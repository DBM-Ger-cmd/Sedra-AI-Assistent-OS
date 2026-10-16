"""Trusted SDK worker. Guest commands never become subprocess commands on the host."""
from __future__ import annotations
import asyncio
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


async def pinned_cached_image(sdk, pinned):
    """Look up `name@sha256:…` in the local cache and prove the digest. The SDK (0.7.4) resolves only the plain name, not the
    pinned form (measured 2026-10-02), so the name is looked up and the digest is compared here; a mismatch is refused."""
    name, expected = pinned.split('@', 1)
    image = await sdk.Image.get(name)
    if image.manifest_digest != expected:
        raise RuntimeError('cached_image_digest_mismatch')
    return name, image


async def copy_tree_into(sb, source, guest_root):
    """Copy the host source tree into the guest. The SDK's copy_from_host takes single files only (a directory fails with
    "access denied" on Windows, measured 2026-10-02), so directories are created and files written one by one.
    Symlinks are skipped: the broker already refused them when it built the source."""
    source = Path(source)
    await sb.fs.mkdir(guest_root)
    for path in sorted(source.rglob('*')):
        if path.is_symlink(): continue
        guest = guest_root + '/' + path.relative_to(source).as_posix()
        if path.is_dir(): await sb.fs.mkdir(guest)
        elif path.is_file(): await sb.fs.write(guest, path.read_bytes())


GUEST_USER = '65534'
MAX_EXPORT_DIR_DEPTH = 8


async def expand_export_dirs(sb, dirs, policy):
    """Directory export (DevVM Phase 1, 2026-10-06; only when the Captain set `allow_export_dirs: true` in config/sandbox.yaml).
    Lists the approved guest directories with the SDK (no guest command) and returns the relative paths of every regular file in them.
    Fails closed: a symlink or special file, more than `max_files` files, a depth over 8, or a path outside /workspace refuses the whole export.
    The broker checks every returned path again against the approved directories before it writes anything (`_candidate`)."""
    found, todo = [], [(d, 0) for d in dirs]
    while todo:
        directory, depth = todo.pop()
        if depth > MAX_EXPORT_DIR_DEPTH: raise RuntimeError('guest_export_dir_too_deep')
        parts = directory.split('/')
        if directory.startswith('/') or '..' in parts or '' in parts: raise RuntimeError('guest_export_dir_invalid')
        for entry in await sb.fs.list('/workspace/' + directory):
            name = str(entry.path).replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]      # the SDK may report a full path or a bare name
            rel = directory + '/' + name
            kind = str(entry.kind).lower()
            if kind.endswith('directory'): todo.append((rel, depth + 1))
            elif kind.endswith('file'): found.append(rel)
            elif kind.endswith('symlink'): raise RuntimeError('guest_export_symlink')
            else: raise RuntimeError('guest_export_special_file')
            if len(found) > policy['max_files']: raise RuntimeError('guest_export_file_count_limit')
    return sorted(found)


def sandbox_name(job_id):
    """Short, stable VM name. msb builds paths like <MSB_HOME>\\sandboxes\\<name>\\runtime\\.runtime-boot-id.<pid>.<n>.tmp and is not
    long-path aware: with GUPPI's project folder a 43-character name gave a 262-character path and the start failed with
    "path not found" (2026-10-02). 12 hex digits of the job id's SHA-256 keep it short and unique enough per host."""
    return 'guppi-' + hashlib.sha256(job_id.encode('utf-8')).hexdigest()[:12]


async def protect_runtime_share(sb):
    """microsandbox shares the sandbox's own host folder at /.msb (virtiofs, mode 777): an unprivileged guest could write host
    files that the host-side `msb` reads (boundary check 2026-10-02). Make it root-only, then prove the guest user is locked out;
    if it is not, no guest command runs (fail closed)."""
    locked = await sb.exec('/bin/chmod', ['0700', '/.msb'], timeout=5)
    if not locked.success: raise RuntimeError('runtime_share_protect_failed')
    probe = await sb.exec('/bin/sh', ['-c', 'echo x > /.msb/.guppi_write_probe'], user=GUEST_USER, timeout=5)
    if probe.success: raise RuntimeError('runtime_share_writable_by_guest')


async def run_job(request, sdk):
    p = request['policy']
    name = sandbox_name(request['job_id'])
    sb = None
    result = {'status': 'FAILED', 'cleanup_confirmed': True, 'commands': [], 'exports': []}
    try:
        # Inspection and NEVER policy refuse network image acquisition.
        image_name, _ = await pinned_cached_image(sdk, p['image'])
        result['cleanup_confirmed'] = False
        sb = await sdk.Sandbox.create(
            name, image=sdk.Image.oci(image_name, root_disk=sdk.RootDisk.tmpfs(p['root_disk_mib'])),
            cpus=p['cpus'], max_cpus=p['cpus'], memory=p['memory_mib'], max_memory=p['memory_mib'],
            network=sdk.Network.none(), security=sdk.SecurityProfile.RESTRICTED,
            pull_policy=sdk.PullPolicy.NEVER, max_duration=float(p['job_timeout_seconds']),
            volumes={}, ports={}, vsock={}, secrets=[], env={}, detached=False, ephemeral=True)
        result['cleanup_confirmed'] = False
        await copy_tree_into(sb, request['source'], '/workspace')
        chmod = await sb.exec('/bin/chmod', ['-R', 'a+rwX', '/workspace'], timeout=5)
        if not chmod.success: raise RuntimeError('workspace_permissions_failed')
        await protect_runtime_share(sb)
        for argv in request['commands']:
            handle = await sb.exec_stream(argv[0], argv[1:], cwd='/workspace', user=GUEST_USER,
                env={'HOME': '/workspace', 'PYTHONDONTWRITEBYTECODE': '1'},
                timeout=float(p['command_timeout_seconds']),
                rlimits=[sdk.Rlimit.nproc(p['max_processes']), sdk.Rlimit.nofile(128),
                         sdk.Rlimit.fsize(p['max_file_bytes']), sdk.Rlimit.cpu(p['command_timeout_seconds'])])
            chunks, count, exit_code = [], 0, None
            async def drain():
                nonlocal count, exit_code
                async for event in handle:
                    # The exit code arrives as an `exited` event; after the stream ends, wait() has nothing left (SDK 0.7.4).
                    if getattr(event, 'code', None) is not None: exit_code = event.code
                    data = event.data
                    if data:
                        count += len(data)
                        if count > p['max_log_bytes']:
                            await handle.kill()
                            raise RuntimeError('command_output_limit')
                        chunks.append(data)
            timed_out = False
            try:
                # exec_stream does not enforce its own timeout (measured 2026-10-02: `sleep 20` with timeout 3 kept running).
                await asyncio.wait_for(drain(), float(p['command_timeout_seconds']))
            except asyncio.TimeoutError:
                timed_out = True
                await handle.kill()
            if timed_out:
                code, success = None, False
            elif exit_code is not None:
                code, success = exit_code, exit_code == 0
            else:
                code, success = await handle.wait()
            result['commands'].append({'argv': argv, 'exit_code': code, 'success': success, 'timed_out': timed_out,
                                       'output': b''.join(chunks).decode('utf-8', errors='replace')})
            if timed_out: raise RuntimeError('guest_command_timeout')
            if not success: raise RuntimeError('guest_command_failed')
        exported, total = [], 0
        export_list = list(request['exports'])
        if request.get('export_dirs'):
            if p.get('allow_export_dirs') is not True: raise RuntimeError('export_dirs_disabled_by_policy')
            export_list += await expand_export_dirs(sb, request['export_dirs'], p)
            if len(export_list) > p['max_files']: raise RuntimeError('guest_export_file_count_limit')
        for rel in export_list:
            guest = '/workspace/' + rel
            # Refuse symlinks on every path component (not just the leaf).
            parts = rel.split('/')
            for index in range(len(parts)):
                info = await sb.fs.stat('/workspace/' + '/'.join(parts[:index+1]))
                if str(info.kind) == 'symlink': raise RuntimeError('guest_export_symlink')
            info = await sb.fs.stat(guest)
            if str(info.kind) != 'file' or info.size > p['max_file_bytes']:
                raise RuntimeError('guest_export_not_regular_or_oversize')
            stream = await sb.fs.read_stream(guest)
            parts, size = [], 0
            async for block in stream:
                size += len(block); total += len(block)
                if size > p['max_file_bytes'] or total > p['max_export_bytes']:
                    raise RuntimeError('guest_export_size_limit')
                parts.append(block)
            exported.append({'path': rel, 'data_base64': base64.b64encode(b''.join(parts)).decode('ascii')})
        result.update({'status': 'PASS', 'exports': exported})
    except asyncio.CancelledError:
        result.update({'status': 'CANCELLED', 'error': 'deadline_or_cancel', 'exports': []})
    except Exception as exc:
        result.update({'status': 'FAILED', 'error': f'{type(exc).__name__}:{exc}', 'exports': []})
    finally:
        if sb is None and result['cleanup_confirmed'] is False:
            # Start failed after the launch was attempted (seen on Windows: "sandbox process exited ... before agent relay
            # became available"). Only an explicit "not found" from the SDK proves nothing is left; anything else stays unconfirmed.
            try:
                await asyncio.wait_for(sdk.Sandbox.get(name), p['cleanup_timeout_seconds'])
            except Exception as exc:
                if type(exc).__name__ == 'SandboxNotFoundError': result['cleanup_confirmed'] = True
        if sb is not None:
            try:
                await asyncio.wait_for(sb.stop(timeout=p['cleanup_timeout_seconds']), p['cleanup_timeout_seconds'])
                result['cleanup_confirmed'] = True
                try:
                    await asyncio.wait_for(sdk.Sandbox.remove(name), p['cleanup_timeout_seconds'])
                except Exception as exc:
                    # An ephemeral sandbox removes itself on stop; "not found" after a confirmed stop means it is gone.
                    if type(exc).__name__ != 'SandboxNotFoundError': raise
            except Exception as exc:
                earlier = result.get('error')          # keep the reason the job failed; the cleanup failure is reported next to it
                result.update({'status': 'CLEANUP_UNCONFIRMED', 'cleanup_confirmed': False,
                               'error': f'cleanup:{type(exc).__name__}:{exc}' + (f' | job:{earlier}' if earlier else ''), 'exports': []})
    if result['cleanup_confirmed'] is not True:
        result['status'] = 'CLEANUP_UNCONFIRMED'
        result['exports'] = []
    return result


async def supervise(request, sdk):
    task = asyncio.create_task(run_job(request, sdk))
    async def watch():
        while not (Path(request['job_root'])/'cancel').exists():
            await asyncio.sleep(0.1)
    watcher = asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait([task, watcher], timeout=request['policy']['job_timeout_seconds'],
                                     return_when=asyncio.FIRST_COMPLETED)
        if task not in done: task.cancel()
        return await task
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)


async def import_image(request, sdk):
    try:
        await sdk.Image.load(request['archive'])
        try:
            _, image = await pinned_cached_image(sdk, request['image_reference'])
        except RuntimeError as exc:
            raise RuntimeError('loaded_image_digest_mismatch') from exc
        return {'status':'PASS','operation_confirmed':True,'image_reference':request['image_reference'],
                'manifest_digest':image.manifest_digest,'vm_started':False}
    except Exception as exc:
        return {'status':'FAILED','operation_confirmed':True,'error':f'{type(exc).__name__}:{exc}','vm_started':False}


def main():
    _, mode, input_path, output_path = sys.argv
    output = Path(output_path)
    dispatched = False
    try:
        if mode not in {'run', 'import_image'}: raise ValueError('unsupported_worker_mode')
        if importlib.metadata.version('microsandbox') != '0.7.4':
            raise RuntimeError('pinned_sdk_required')
        import microsandbox as sdk
        if sdk.version() != '0.7.4': raise RuntimeError('native_sdk_version_mismatch')
        sdk.set_default_backend(sdk.BackendKind.LOCAL)
        # Explicit package runtime paths win over ambient installations.
        from microsandbox._runtime import msb_path
        sdk._microsandbox.set_runtime_msb_path(str(msb_path()))
        library_dir = msb_path().parent.parent / 'lib'
        libraries = [p for p in library_dir.iterdir() if 'krunfw' in p.name and p.is_file()]
        if len(libraries) != 1: raise RuntimeError('bundled_firmware_missing_or_ambiguous')
        sdk.set_libkrunfw_path(str(libraries[0]))
        request = json.loads(Path(input_path).read_text(encoding='utf-8'))
        dispatched = True
        result = asyncio.run(supervise(request, sdk) if mode == 'run' else import_image(request, sdk))
    except Exception as exc:
        result = {'status': 'FAILED', 'error': f'{type(exc).__name__}:{exc}',
                  'cleanup_confirmed': True, 'commands': [], 'exports': []}
        if mode == 'import_image':
            # Failing during SDK setup, before any image call, is a known outcome: nothing was imported.
            result.update(operation_confirmed=not dispatched, vm_started=False)
    save(output, result)


if __name__ == '__main__': main()
