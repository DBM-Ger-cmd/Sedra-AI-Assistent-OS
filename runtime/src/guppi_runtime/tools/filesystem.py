from __future__ import annotations
from pathlib import Path
import codecs
import hashlib
import os
import shutil
import tempfile
from ..request_binding import file_request
from .base import BaseTool, ToolValidationError


def _codec(args):
    """The text encoding of a request. An unknown name or a name that is no text codec is a validation error, not a crash."""
    name = args.get("encoding", "utf-8")
    try:
        codecs.lookup(name)
        "".encode(name)
    except (LookupError, TypeError):
        raise ToolValidationError("invalid_encoding")
    return name


class FilesystemTool(BaseTool):
    id = "filesystem"
    version = "0.2.0"
    supported_operations = {"read_text", "list_dir", "stat", "sha256", "mkdir", "write_text", "copy", "move", "delete"}

    def __init__(self, root: Path, guard=None, audit=None, max_read_bytes: int = 2_000_000, max_write_bytes: int = 4_000_000):
        super().__init__(root, guard, audit)
        self.max_read_bytes = int(max_read_bytes)
        self.max_write_bytes = int(max_write_bytes)

    def execute(self, mission_id: str, operation: str, args=None, approval_token=None):
        args = args or {}
        handlers = {
            "read_text": lambda: self.read_text(mission_id, args),
            "list_dir": lambda: self.list_dir(mission_id, args),
            "stat": lambda: self.stat(mission_id, args),
            "sha256": lambda: self.sha256(mission_id, args),
            "mkdir": lambda: self.mkdir(mission_id, args, approval_token),
            "write_text": lambda: self.write_text(mission_id, args, approval_token),
            "copy": lambda: self.copy(mission_id, args, approval_token),
            "move": lambda: self.move(mission_id, args, approval_token),
            "delete": lambda: self.delete(mission_id, args, approval_token),
        }
        if operation not in handlers:
            raise ToolValidationError(f"unsupported_filesystem_operation:{operation}")
        return handlers[operation]()

    def _guard(self, action, mission_id, target, approval_token=None, *, risks=None, rollback_available=False, request_binding=None):
        verdict = self.guard.evaluate(action, mission_id=mission_id, target=str(target)) if self.guard else {"decision":"ALLOW"}
        if verdict["decision"] == "BLOCK":
            return {"status":"blocked", "guard":verdict}
        if verdict["decision"] == "CAPTAIN_REQUIRED":
            auth = self.guard.authorize(approval_token, mission_id=mission_id, action=action, target=str(target),request_binding=request_binding) if self.guard else {"authorized":False}
            if not auth["authorized"]:
                gate = self.guard.create_gate(mission_id, action, str(target), risks=risks or [], rollback_available=rollback_available,request_binding=request_binding)
                return {"status":"captain_required", "guard":verdict, "gate":gate}
        return None

    def read_text(self, mission_id: str, args):
        path = self._resolve(args.get("path", ""), must_exist=True)
        if not path.is_file():
            raise ToolValidationError("not_a_file")
        encoding = _codec(args)
        size = path.stat().st_size
        limit=args.get('max_bytes',self.max_read_bytes)
        if type(limit) is not int or not 1 <= limit <= self.max_read_bytes:
            raise ToolValidationError('invalid_read_byte_limit')
        if size > limit:
            raise ToolValidationError("file_too_large")
        blocked = self._guard("read_project_file", mission_id, path)
        if blocked:
            return blocked
        if 'max_bytes' in args:
            with path.open('rb') as stream: raw=stream.read(limit+1)
            if len(raw)>limit: raise ToolValidationError('file_too_large')
            content=self._decode(raw,encoding)
            size=len(raw)
        else:
            content = self._decode(path.read_bytes(),encoding)
        self._audit("TOOL_CALLED", mission_id, {"tool":self.id,"operation":"read_text","path":str(path),"bytes":size})
        return {"status":"completed","path":str(path),"content":content,"bytes":size}

    @staticmethod
    def _decode(raw, encoding):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            raise ToolValidationError("file_not_decodable")

    def list_dir(self, mission_id: str, args):
        path = self._resolve(args.get("path", "."), must_exist=True)
        if not path.is_dir():
            raise ToolValidationError("not_a_directory")
        blocked = self._guard("read_project_file", mission_id, path)
        if blocked:
            return blocked
        entries=[]
        limit=max(1,min(int(args.get("limit",1000)),5000))
        if args.get('bounded') is True:
            with os.scandir(path) as scanner:
                for entry in scanner:
                    if len(entries)>limit:break
                    kind='symlink' if entry.is_symlink() else 'dir' if entry.is_dir(follow_symlinks=False) else 'file' if entry.is_file(follow_symlinks=False) else 'special'
                    entries.append({'name':entry.name,'type':kind,'size':entry.stat(follow_symlinks=False).st_size if kind=='file' else None})
            truncated=len(entries)>limit
            self._audit('TOOL_CALLED',mission_id,{'tool':self.id,'operation':'list_dir','path':str(path),'entries':min(len(entries),limit),'bounded':True})
            return {'status':'completed','path':str(path),'entries':sorted(entries[:limit],key=lambda x:x['name']), 'truncated':truncated}
        children=sorted(path.iterdir(), key=lambda x: x.name.lower())      # one listing: the truncation flag must not read the directory a second time
        for p in children[:limit]:
            entries.append({"name":p.name,"type":"dir" if p.is_dir() else "file","size":None if p.is_dir() else p.stat().st_size})
        self._audit("TOOL_CALLED", mission_id, {"tool":self.id,"operation":"list_dir","path":str(path),"entries":len(entries)})
        return {"status":"completed","path":str(path),"entries":entries,"truncated":len(children)>limit}

    def stat(self, mission_id: str, args):
        path=self._resolve(args.get("path", ""), must_exist=True)
        blocked=self._guard("read_project_file",mission_id,path)
        if blocked: return blocked
        st=path.stat()
        result={"status":"completed","path":str(path),"type":"dir" if path.is_dir() else "file","size":st.st_size,"mtime_ns":st.st_mtime_ns}
        self._audit("TOOL_CALLED",mission_id,{"tool":self.id,"operation":"stat","path":str(path)})
        return result

    def sha256(self, mission_id: str, args):
        path=self._resolve(args.get("path", ""), must_exist=True)
        if not path.is_file(): raise ToolValidationError("not_a_file")
        blocked=self._guard("read_project_file",mission_id,path)
        if blocked: return blocked
        h=hashlib.sha256()
        limit=args.get('max_bytes')
        if limit is not None and (type(limit) is not int or not 1<=limit<=self.max_read_bytes):
            raise ToolValidationError('invalid_hash_byte_limit')
        count=0
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(min(1024*1024,limit+1) if limit is not None else 1024*1024),b""):
                count+=len(chunk)
                if limit is not None and count>limit:raise ToolValidationError('file_too_large')
                h.update(chunk)
        digest=h.hexdigest()
        self._audit("TOOL_CALLED",mission_id,{"tool":self.id,"operation":"sha256","path":str(path)})
        return {"status":"completed","path":str(path),"sha256":digest}

    def mkdir(self, mission_id: str, args, approval_token=None):
        path=self._resolve(args.get("path", ""), must_exist=False)
        if path.exists():
            if path.is_dir(): return {"status":"completed","path":str(path),"created":False}
            raise ToolValidationError("mkdir_target_is_file")
        blocked=self._guard("create_new_artifact",mission_id,path,approval_token,rollback_available=True,request_binding=file_request("mkdir",args,path))
        if blocked: return blocked
        path.mkdir(parents=bool(args.get("parents",True)),exist_ok=False)
        self._audit("ARTIFACT_CREATED",mission_id,{"tool":self.id,"operation":"mkdir","path":str(path)})
        return {"status":"completed","path":str(path),"created":True}

    def write_text(self, mission_id: str, args, approval_token=None):
        if "content" not in args:
            raise ToolValidationError("missing_content")
        content=str(args["content"])
        try:
            encoded=content.encode(_codec(args))
        except UnicodeEncodeError:
            raise ToolValidationError("content_not_encodable")
        if len(encoded)>self.max_write_bytes:
            raise ToolValidationError("content_too_large")
        path = self._resolve(args.get("path", ""), must_exist=False)
        if path.exists() and path.is_dir():
            raise ToolValidationError("write_target_is_directory")
        expected=args.get("expected_sha256")
        if expected is not None and path.exists():
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != str(expected):
                raise ToolValidationError("precondition_sha256_mismatch")
        action = "overwrite_existing" if path.exists() else "create_new_artifact"
        blocked=self._guard(action,mission_id,path,approval_token,rollback_available=True,request_binding=file_request("write_text",args,path))
        if blocked: return blocked
        path.parent.mkdir(parents=True, exist_ok=True)
        fd,tmp_name=tempfile.mkstemp(prefix=f".{path.name}.",suffix=".tmp",dir=str(path.parent))
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(encoded); f.flush(); os.fsync(f.fileno())
            os.replace(tmp_name,path)
        finally:
            if os.path.exists(tmp_name): os.unlink(tmp_name)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        self._audit("ARTIFACT_MODIFIED" if action=="overwrite_existing" else "ARTIFACT_CREATED", mission_id, {"tool":self.id,"operation":"write_text","path":str(path),"action":action,"sha256":digest})
        return {"status":"completed","path":str(path),"action":action,"bytes":path.stat().st_size,"sha256":digest}

    def copy(self, mission_id: str, args, approval_token=None):
        src=self._resolve(args.get("src", ""),must_exist=True)
        dst=self._resolve(args.get("dst", ""),must_exist=False)
        if not src.is_file(): raise ToolValidationError("copy_source_not_file")
        if dst.exists() and dst.is_dir(): raise ToolValidationError("copy_target_is_directory")
        action="overwrite_existing" if dst.exists() else "create_new_artifact"
        blocked=self._guard(action,mission_id,dst,approval_token,rollback_available=True,request_binding=file_request("copy",args,src,dst))
        if blocked: return blocked
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        digest=hashlib.sha256(dst.read_bytes()).hexdigest()
        self._audit("ARTIFACT_MODIFIED" if action=="overwrite_existing" else "ARTIFACT_CREATED",mission_id,{"tool":self.id,"operation":"copy","src":str(src),"dst":str(dst),"sha256":digest})
        return {"status":"completed","src":str(src),"path":str(dst),"action":action,"sha256":digest}

    def move(self, mission_id: str, args, approval_token=None):
        src=self._resolve(args.get("src", ""),must_exist=True)
        dst=self._resolve(args.get("dst", ""),must_exist=False)
        if dst.exists(): raise ToolValidationError("move_target_exists")
        scope=f"{src}->{dst}"
        blocked=self._guard("filesystem_move",mission_id,scope,approval_token,risks=["Moves an existing artifact"],rollback_available=True,request_binding=file_request("move",args,src,dst))
        if blocked: return blocked
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(src),str(dst))
        self._audit("ARTIFACT_MODIFIED",mission_id,{"tool":self.id,"operation":"move","src":str(src),"dst":str(dst)})
        return {"status":"completed","src":str(src),"path":str(dst)}

    def delete(self, mission_id: str, args, approval_token=None):
        path = self._resolve(args.get("path", ""), must_exist=True)
        if path == self.root:
            raise ToolValidationError("cannot_delete_tool_root")
        blocked=self._guard("file_delete",mission_id,path,approval_token,risks=["Deletes an existing path"],rollback_available=False,request_binding=file_request("delete",args,path))
        if blocked: return blocked
        if path.is_dir():
            if not bool(args.get("recursive",False)) and any(path.iterdir()):
                raise ToolValidationError("directory_not_empty_recursive_required")
            shutil.rmtree(path)
        else:
            path.unlink()
        self._audit("TOOL_CALLED", mission_id, {"tool":self.id,"operation":"delete","path":str(path)})
        return {"status":"completed","path":str(path)}
