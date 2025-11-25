"""
CLI Controller 예제

CLI 명령어 사용 예제를 보여줍니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cli.cli_controller import CLIController

def main():
    """CLI 예제 실행"""
    controller = CLIController()
    
    print("=" * 60)
    print("CLI Controller 예제")
    print("=" * 60)
    
    # 도움말 출력
    print("\n[도움말 출력]")
    controller.parser.print_help()
    
    # analyze 명령어 예제 (실제로는 설정 파일이 필요)
    print("\n" + "=" * 60)
    print("analyze 명령어 예제")
    print("=" * 60)
    print("사용법: python -m src.cli.cli_controller analyze --config config.json")
    
    # list 명령어 예제
    print("\n" + "=" * 60)
    print("list 명령어 예제")
    print("=" * 60)
    print("사용법:")
    print("  python -m src.cli.cli_controller list --all")
    print("  python -m src.cli.cli_controller list --db")
    print("  python -m src.cli.cli_controller list --modified")
    print("  python -m src.cli.cli_controller list --endpoint")
    print("  python -m src.cli.cli_controller list --callgraph UserController.getUser")
    
    # modify 명령어 예제
    print("\n" + "=" * 60)
    print("modify 명령어 예제")
    print("=" * 60)
    print("사용법:")
    print("  python -m src.cli.cli_controller modify --config config.json")
    print("  python -m src.cli.cli_controller modify --config config.json --dry-run")

if __name__ == "__main__":
    main()

