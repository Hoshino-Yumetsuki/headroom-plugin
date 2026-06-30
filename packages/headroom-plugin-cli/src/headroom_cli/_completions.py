"""Shell completion script generators."""
from __future__ import annotations


def bash_completions() -> str:
    """Generate bash completion script."""
    return (
        '_headroom_cli() {\n'
        '    local commands="list diagnose treat strategy guard doctor formulary init completions"\n'
        '    local rx_tiers="gentle standard aggressive"\n'
        '    COMPREPLY=()\n'
        '    local cur="${COMP_WORDS[COMP_CWORD]}"\n'
        '    local prev="${COMP_WORDS[COMP_CWORD-1]}"\n'
        '    if [ "$COMP_CWORD" -eq 1 ]; then\n'
        '        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )\n'
        '    elif [ "$prev" = "--rx" ]; then\n'
        '        COMPREPLY=( $(compgen -W "$rx_tiers" -- "$cur") )\n'
        '    fi\n'
        '}\n'
        'complete -F _headroom_cli headroom-cli'
    )


def zsh_completions() -> str:
    """Generate zsh completion script."""
    return (
        '#compdef headroom-cli\n'
        '_headroom_cli() {\n'
        '    local -a commands\n'
        '    commands=(\n'
        "        'list:List sessions'\n"
        "        'diagnose:Analyze bloat'\n"
        "        'treat:Run prescription'\n"
        "        'strategy:Run single strategy'\n"
        "        'guard:Start guard daemon'\n"
        "        'doctor:Health check'\n"
        "        'formulary:Show strategies'\n"
        "        'init:First-time setup'\n"
        "        'completions:Shell completions'\n"
        '    )\n'
        "    _describe 'command' commands\n"
        '}\n'
        '_headroom_cli "$@"'
    )


def fish_completions() -> str:
    """Generate fish completion script."""
    lines = [
        "complete -c headroom-cli -n '__fish_use_subcommand' -a list -d 'List sessions'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a diagnose -d 'Analyze bloat'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a treat -d 'Run prescription'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a strategy -d 'Run single strategy'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a guard -d 'Start guard daemon'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a doctor -d 'Health check'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a formulary -d 'Show strategies'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a init -d 'First-time setup'",
        "complete -c headroom-cli -n '__fish_use_subcommand' -a completions -d 'Shell completions'",
    ]
    return "\n".join(lines)
