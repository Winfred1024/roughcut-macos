"""Select the isolated runtime, then execute the installed CLI."""
import argparse
import os
from pathlib import Path
import sys
from mac_common import CONFIG_PATH, env_for, load_config


def main():
    ap = argparse.ArgumentParser(description='粗剪命令行：probe / transcribe / build')
    ap.add_argument('--config', default=str(CONFIG_PATH))
    ap.add_argument('command', choices=['probe', 'transcribe', 'build'])
    args, rest = ap.parse_known_args()
    c = load_config(args.config)
    exe = c.get('asrenv') if args.command == 'transcribe' else c['jyenv']
    if not exe or not Path(exe).is_file():
        raise RuntimeError('对应运行环境尚未安装；ASR 需要不带 --no-model 重新安装')
    cli = Path(c['skill_dir']) / 'scripts/roughcut_cli.py'
    os.execve(exe, [exe, str(cli), args.command, *rest], env_for(c))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)
