$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
python "$ScriptDir\install.py" $args
