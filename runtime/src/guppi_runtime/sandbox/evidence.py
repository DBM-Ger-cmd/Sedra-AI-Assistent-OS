"""Validate worker claims against the approved command contract; no guest execution."""
from ..tools.base import ToolValidationError


def validate_pass(result, plan):
    if not isinstance(result, dict) or result.get('status') != 'PASS':
        raise ToolValidationError('sandbox_pass_required')
    if result.get('cleanup_confirmed') is not True:
        raise ToolValidationError('sandbox_cleanup_unconfirmed')
    if result.get('error') is not None:
        raise ToolValidationError('sandbox_pass_with_error')
    commands = result.get('commands')
    expected = plan['request']['commands']
    if not isinstance(commands, list) or len(commands) != len(expected):
        raise ToolValidationError('sandbox_command_count_mismatch')
    total = 0
    for observed, argv in zip(commands, expected):
        if not isinstance(observed, dict) or observed.get('argv') != argv:
            raise ToolValidationError('sandbox_command_identity_mismatch')
        if type(observed.get('exit_code')) is not int or observed['exit_code'] != 0 or observed.get('success') is not True:
            raise ToolValidationError('sandbox_command_not_successful')
        output = observed.get('output')
        if not isinstance(output, str):
            raise ToolValidationError('sandbox_command_output_invalid')
        total += len(output.encode('utf-8'))
        # Replacement decoding may expand invalid UTF-8 by up to three times.
        if total > 3 * plan['policy']['max_log_bytes']:
            raise ToolValidationError('sandbox_command_output_limit')
    return True
