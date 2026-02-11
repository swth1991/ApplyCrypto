"""
Anyframe Context Generator 검증 스크립트

실제 타겟 프로젝트의 table_access_info.json을 읽어서
AnyframeContextGenerator(import-chasing 기반)가
어떤 파일들을 context로 묶어서 LLM에게 전달하는지 검증합니다.

지원하는 sql_wrapping_type:
    - jdbc: Anyframe 온라인용 (SVC, BIZ, DQM, DEM 레이어)

사용법:
    python examples/run_anyframe_context_generator.py --config /path/to/config.json

옵션:
    --config: config.json 파일 경로 (필수)
    --table: 특정 테이블만 검증 (선택, 기본값: 전체)
    --output: 결과를 저장할 파일 경로 (선택)
    --verbose: 상세 로그 출력 (선택)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Set
from unittest.mock import MagicMock

# Add src to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root / "src"))

from config.config_manager import Configuration, load_config
from models.table_access_info import TableAccessInfo
from models.modification_context import ModificationContext
from modifier.context_generator.anyframe_context_generator import (
    AnyframeContextGenerator,
)
from modifier.context_generator.base_context_generator import BaseContextGenerator


class TeeStream:
    """stdout을 콘솔과 파일 양쪽에 동시 출력하는 래퍼"""

    def __init__(self, original, file_path):
        self.original = original
        self.file = open(file_path, "a", encoding="utf-8")

    def write(self, text):
        self.original.write(text)
        self.file.write(text)

    def flush(self):
        self.original.flush()
        self.file.flush()

    def close(self):
        self.file.close()


def setup_logging(verbose: bool = False, log_file: str = None):
    """로깅 설정

    기본 모드: 테스트 스크립트 출력만 표시, context generator 내부 로그는 숨김
    verbose 모드(-v): context generator 내부 로그도 표시
    log_file: 지정 시 print() + 로그 모두 파일에 저장
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not verbose:
        # 콘솔에는 context generator 내부 로그 숨김
        logging.getLogger("applycrypto").setLevel(logging.WARNING)
        logging.getLogger("applycrypto.anyframe_context_generator").setLevel(logging.WARNING)
        logging.getLogger("applycrypto.context_generator").setLevel(logging.WARNING)

    if log_file:
        # 1) 로그 파일 초기화
        with open(log_file, "w", encoding="utf-8"):
            pass

        # 2) logging → 파일 (DEBUG 레벨, 콘솔 레벨과 독립)
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().setLevel(logging.DEBUG)

        # 3) print() → 파일 (콘솔에도 동시 출력)
        sys.stdout = TeeStream(sys.stdout, log_file)

    return logging.getLogger("run_anyframe_context_generator")


def load_table_access_info(config: Configuration) -> List[TableAccessInfo]:
    """
    타겟 프로젝트의 table_access_info.json 파일 로드

    Args:
        config: Configuration 객체

    Returns:
        List[TableAccessInfo]: 테이블 접근 정보 목록
    """
    target_project = Path(config.target_project)
    json_path = target_project / ".applycrypto" / "results" / "table_access_info.json"

    if not json_path.exists():
        raise FileNotFoundError(
            f"table_access_info.json을 찾을 수 없습니다: {json_path}\n"
            "'analyze' 명령어를 먼저 실행하세요."
        )

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    table_access_info_list = []
    for item in data:
        if isinstance(item, dict):
            table_access_info_list.append(TableAccessInfo.from_dict(item))

    return table_access_info_list


def create_mock_code_generator(config: Configuration) -> MagicMock:
    """
    Mock CodeGenerator 생성 (실제 LLM 호출 없이 테스트)

    Args:
        config: Configuration 객체

    Returns:
        MagicMock: Mock CodeGenerator
    """
    mock_code_generator = MagicMock()
    mock_code_generator.calculate_token_size.return_value = 100
    mock_code_generator.create_prompt.return_value = "Mock Prompt"
    return mock_code_generator


def create_context_generator(
    config: Configuration,
    mock_code_generator: MagicMock,
) -> BaseContextGenerator:
    """
    sql_wrapping_type에 따라 적절한 Context Generator 생성

    Args:
        config: Configuration 객체
        mock_code_generator: Mock CodeGenerator

    Returns:
        BaseContextGenerator: Context Generator 인스턴스
    """
    if config.sql_wrapping_type in ("jdbc", "jpa"):
        return AnyframeContextGenerator(config, mock_code_generator)
    else:
        raise ValueError(
            f"이 스크립트는 jdbc, jpa만 지원합니다. "
            f"현재 sql_wrapping_type: {config.sql_wrapping_type}"
        )


def run_context_generator(
    config: Configuration,
    table_access_info: TableAccessInfo,
    logger: logging.Logger,
) -> List[ModificationContext]:
    """
    Context Generator 실행

    Args:
        config: Configuration 객체
        table_access_info: 테이블 접근 정보
        logger: 로거

    Returns:
        List[ModificationContext]: 생성된 context 목록
    """
    mock_code_generator = create_mock_code_generator(config)
    generator = create_context_generator(config, mock_code_generator)
    logger.info(f"사용 중인 Context Generator: {generator.__class__.__name__}")

    contexts = generator.generate(
        layer_files=table_access_info.layer_files,
        table_name=table_access_info.table_name,
        columns=table_access_info.columns,
        table_access_info=table_access_info,
    )

    return contexts


def extract_layer_from_path(file_path: str) -> str:
    """
    파일 경로에서 레이어 힌트 추출

    Args:
        file_path: 파일 경로

    Returns:
        str: 레이어 힌트
    """
    path_lower = file_path.lower().replace("\\", "/")
    filename = Path(file_path).name
    stem = Path(file_path).stem

    # Anyframe 레이어 패턴 (디렉토리 기반)
    if "/svc/" in path_lower:
        if "/impl/" in path_lower or stem.endswith("Impl"):
            return "SVCImpl"
        if stem.endswith("SVO") or stem.endswith("VO") or stem.endswith("DVO"):
            return "SVO"
        return "SVC"
    elif "/biz/" in path_lower:
        if stem.endswith("BVO"):
            return "BVO"
        if stem.endswith("BIZ"):
            return "BIZ"
        if "Util" in stem:
            return "Util"
        return "BIZ-etc"
    elif "/dqm/" in path_lower:
        if stem.endswith("DVO"):
            return "DVO"
        return "DQM"
    elif "/dem/" in path_lower:
        return "DEM"
    elif "/ctl/" in path_lower:
        return "CTL"

    # 파일명 패턴 기반 fallback
    if stem.endswith("SVCImpl"):
        return "SVCImpl"
    elif stem.endswith("SVC"):
        return "SVC"
    elif stem.endswith("BIZ"):
        return "BIZ"
    elif stem.endswith("DQM"):
        return "DQM"
    elif stem.endswith("DEM"):
        return "DEM"
    elif stem.endswith("VO") or stem.endswith("SVO") or stem.endswith("DVO"):
        return "VO"

    return "OTHER"


def print_call_stacks_summary(
    table_info: TableAccessInfo,
    logger: logging.Logger,
):
    """
    call_stacks 요약 출력 — BIZ 파일 어떤 메서드가 참조되는지 확인

    Args:
        table_info: 테이블 접근 정보
        logger: 로거
    """
    biz_methods: Dict[str, Set[str]] = {}  # {ClassName: {method1, method2, ...}}
    all_classes: Set[str] = set()

    for sq in table_info.sql_queries:
        for cs in sq.get("call_stacks", []):
            if not isinstance(cs, list):
                continue
            for entry in cs:
                if isinstance(entry, str) and "." in entry:
                    cls_name, method_name = entry.split(".", 1)
                    all_classes.add(cls_name)
                    if cls_name.endswith("BIZ"):
                        if cls_name not in biz_methods:
                            biz_methods[cls_name] = set()
                        biz_methods[cls_name].add(method_name)

    if biz_methods:
        print(f"\n  call_stack에 등장하는 BIZ 클래스 및 메서드:")
        for cls_name, methods in sorted(biz_methods.items()):
            print(f"    {cls_name}: {', '.join(sorted(methods))}")

    # call_stack 시작점(첫 entry) 클래스들
    start_classes: Set[str] = set()
    for sq in table_info.sql_queries:
        for cs in sq.get("call_stacks", []):
            if isinstance(cs, list) and cs:
                first = cs[0]
                if isinstance(first, str) and "." in first:
                    start_classes.add(first.split(".")[0])
    if start_classes:
        print(f"  call_stack 시작점 클래스: {', '.join(sorted(start_classes))}")


def print_context_summary(
    contexts: List[ModificationContext],
    table_name: str,
    logger: logging.Logger,
):
    """
    생성된 context 요약 출력

    Args:
        contexts: ModificationContext 목록
        table_name: 테이블명
        logger: 로거
    """
    print(f"\n{'=' * 70}")
    print(f"테이블: {table_name}")
    print(f"생성된 Context 수: {len(contexts)}")
    print(f"{'=' * 70}")

    for i, ctx in enumerate(contexts, 1):
        print(f"\n[Context {i}] - Layer/Group: {ctx.layer or '(없음)'}")
        print(f"  파일 수: {ctx.file_count}")
        print(f"  Context Files (VO 등): "
              f"{len(ctx.context_files) if ctx.context_files else 0}개")

        # 레이어별 카운트
        layer_counts: Dict[str, int] = {}
        for file_path in ctx.file_paths:
            layer_hint = extract_layer_from_path(file_path)
            layer_counts[layer_hint] = layer_counts.get(layer_hint, 0) + 1

        layer_summary = ", ".join(
            f"{layer}={count}" for layer, count in sorted(layer_counts.items())
        )
        print(f"  레이어 구성: {layer_summary}")

        print("  포함된 파일들:")
        for file_path in ctx.file_paths:
            filename = Path(file_path).name
            layer_hint = extract_layer_from_path(file_path)
            print(f"    - [{layer_hint}] {filename}")

        if ctx.context_files:
            print("  Context Files (수정 대상 아님):")
            total_vo_tokens = 0
            for file_path in ctx.context_files:
                filename = Path(file_path).name
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    file_tokens = len(content) // 4
                    total_vo_tokens += file_tokens
                    print(f"    - [VO] {filename} (~{file_tokens:,} tokens)")
                except Exception:
                    print(f"    - [VO] {filename} (읽기 실패)")

            print(f"  총 VO 토큰 예상: ~{total_vo_tokens:,} tokens")

        print("-" * 70)


def print_biz_filtering_detail(
    table_info: TableAccessInfo,
    logger: logging.Logger,
):
    """
    BIZ 필터링 과정을 상세 출력 (stem 필터 + call_stack 필터)

    Args:
        table_info: 테이블 접근 정보
        logger: 로거
    """
    biz_files_raw = table_info.layer_files.get("biz", [])
    if not biz_files_raw:
        print("  BIZ 파일 없음")
        return

    print(f"\n  === BIZ 필터링 상세 ===")
    print(f"  원본 biz 파일: {len(biz_files_raw)}개")

    # Filter 1: stem이 "BIZ"로 끝나는 것만
    biz_after_stem = [f for f in biz_files_raw if Path(f).stem.endswith("BIZ")]
    excluded_stem = [f for f in biz_files_raw if not Path(f).stem.endswith("BIZ")]
    print(f"  stem 필터 후: {len(biz_after_stem)}개")
    if excluded_stem:
        print(f"    제외 (Util 등): {', '.join(Path(f).name for f in excluded_stem[:10])}")

    # Filter 2: call_stack에 등장하는 BIZ만
    call_stack_classes: set = set()
    for sq in table_info.sql_queries:
        for cs in sq.get("call_stacks", []):
            if not isinstance(cs, list):
                continue
            for entry in cs:
                if isinstance(entry, str) and "." in entry:
                    call_stack_classes.add(entry.split(".")[0])

    biz_after_callstack = [f for f in biz_after_stem if Path(f).stem in call_stack_classes]
    excluded_callstack = [f for f in biz_after_stem if Path(f).stem not in call_stack_classes]
    print(f"  call_stack 필터 후: {len(biz_after_callstack)}개")
    if excluded_callstack:
        print(f"    제외 (다른 테이블 BIZ): "
              f"{', '.join(Path(f).name for f in excluded_callstack[:10])}")

    print(f"  최종 BIZ: {', '.join(Path(f).name for f in biz_after_callstack[:10])}")
    if len(biz_after_callstack) > 10:
        print(f"    ... 외 {len(biz_after_callstack) - 10}개")


def run_endpoint_extraction(
    config: Configuration,
    table_info: TableAccessInfo,
    logger: logging.Logger,
):
    """
    엔드포인트 추출 전략 테스트

    svc 레이어 파일들에서 엔드포인트를 추출합니다.

    Args:
        config: Configuration 객체
        table_info: 테이블 접근 정보
        logger: 로거
    """
    from parser.endpoint_strategy.endpoint_extraction_strategy_factory import (
        EndpointExtractionStrategyFactory,
    )
    from parser.java_ast_parser import JavaASTParser

    java_parser = JavaASTParser()

    try:
        strategy = EndpointExtractionStrategyFactory.create(
            framework_type=config.framework_type,
            java_parser=java_parser,
        )
    except (ValueError, NotImplementedError) as e:
        logger.warning(f"엔드포인트 추출 전략 생성 실패: {e}")
        return

    print(f"\n{'=' * 70}")
    print(f"엔드포인트 추출 테스트 ({strategy.__class__.__name__})")
    print(f"{'=' * 70}")

    # SVC/SVCImpl 파일에서 엔드포인트 추출 시도
    svc_files = table_info.layer_files.get("svc", [])
    if not svc_files:
        print("  SVC 파일이 없습니다.")
        return

    total_endpoints = 0
    for svc_file in svc_files[:10]:  # 최대 10개만
        try:
            tree, error = java_parser.parse_file(Path(svc_file))
            if error:
                continue

            classes = java_parser.extract_class_info(tree, Path(svc_file))
            endpoints = strategy.extract_endpoints_from_classes(classes)

            if endpoints:
                total_endpoints += len(endpoints)
                for ep in endpoints:
                    print(f"  [{Path(svc_file).name}] "
                          f"{ep.method_signature} → {ep.path or '(no path)'}")
        except Exception as e:
            logger.debug(f"엔드포인트 추출 실패: {Path(svc_file).name} - {e}")

    print(f"\n  총 엔드포인트: {total_endpoints}개 (SVC {min(len(svc_files), 10)}개 검사)")


def save_results(
    results: List[dict],
    output_path: Path,
    logger: logging.Logger,
):
    """결과를 JSON 파일로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"결과가 저장되었습니다: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Anyframe Context Generator 검증 스크립트"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="config.json 파일 경로",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        help="특정 테이블만 검증 (선택)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="결과를 저장할 JSON 파일 경로 (선택)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="상세 로그 출력",
    )
    parser.add_argument(
        "--show-endpoints",
        action="store_true",
        help="엔드포인트 추출 테스트 출력",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="로그를 저장할 파일 경로 (콘솔과 별도로 전체 로그 기록)",
    )

    args = parser.parse_args()

    # 로깅 설정
    logger = setup_logging(args.verbose, log_file=args.log_file)

    # Config 로드
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        logger.error(f"Config 파일을 찾을 수 없습니다: {config_path}")
        sys.exit(1)

    try:
        config = load_config(str(config_path))
        logger.info(f"Config 로드 완료: {config_path}")
        logger.info(f"  - framework_type: {config.framework_type}")
        logger.info(f"  - sql_wrapping_type: {config.sql_wrapping_type}")
        logger.info(f"  - modification_type: {config.modification_type}")
    except Exception as e:
        logger.error(f"Config 로드 실패: {e}")
        sys.exit(1)

    # sql_wrapping_type 검증
    supported_types = ["jdbc", "jpa"]
    if config.sql_wrapping_type not in supported_types:
        logger.error(
            f"이 스크립트는 {supported_types}만 지원합니다. "
            f"현재 sql_wrapping_type: {config.sql_wrapping_type}"
        )
        sys.exit(1)

    # table_access_info.json 로드
    try:
        table_access_info_list = load_table_access_info(config)
        logger.info(
            f"table_access_info.json 로드 완료: {len(table_access_info_list)}개 테이블"
        )
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"table_access_info.json 로드 실패: {e}")
        sys.exit(1)

    # 특정 테이블만 필터링
    if args.table:
        table_access_info_list = [
            t
            for t in table_access_info_list
            if t.table_name.lower() == args.table.lower()
        ]
        if not table_access_info_list:
            logger.error(f"테이블 '{args.table}'을 찾을 수 없습니다.")
            sys.exit(1)

    # 결과 수집
    all_results = []

    # 각 테이블에 대해 Context Generator 실행
    for table_info in table_access_info_list:
        logger.info(f"테이블 '{table_info.table_name}' 처리 중...")

        # layer_files가 비어있으면 스킵
        if not table_info.layer_files:
            logger.warning(
                f"테이블 '{table_info.table_name}'에 layer_files가 없습니다. 스킵합니다."
            )
            continue

        # layer_files 정보 출력
        print(f"\n{'=' * 70}")
        print(f"테이블: {table_info.table_name}")
        print(f"입력 layer_files:")
        for layer, files in table_info.layer_files.items():
            print(f"  {layer}: {len(files)}개 파일")
            if args.verbose:
                for f in files[:5]:
                    print(f"    - {Path(f).name}")
                if len(files) > 5:
                    print(f"    ... 외 {len(files) - 5}개")

        # BIZ 필터링 상세 출력
        print_biz_filtering_detail(table_info, logger)

        # call_stacks 요약
        print_call_stacks_summary(table_info, logger)

        # Context 생성
        try:
            contexts = run_context_generator(config, table_info, logger)
        except Exception as e:
            logger.error(f"Context 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            continue

        # 결과 출력
        print_context_summary(contexts, table_info.table_name, logger)

        # 엔드포인트 추출 테스트
        if args.show_endpoints:
            run_endpoint_extraction(config, table_info, logger)

        # 결과 수집
        table_result = {
            "table_name": table_info.table_name,
            "input_layer_files": {
                layer: len(files)
                for layer, files in table_info.layer_files.items()
            },
            "contexts": [
                {
                    "layer": ctx.layer,
                    "file_count": ctx.file_count,
                    "file_paths": ctx.file_paths,
                    "context_files": ctx.context_files or [],
                    "layers": {
                        extract_layer_from_path(fp): 1
                        for fp in ctx.file_paths
                    },
                }
                for ctx in contexts
            ],
        }
        all_results.append(table_result)

    # 전체 요약 출력
    print(f"\n{'=' * 70}")
    print("전체 요약")
    print(f"{'=' * 70}")
    print(f"처리된 테이블 수: {len(all_results)}")
    total_contexts = sum(len(r["contexts"]) for r in all_results)
    print(f"생성된 총 Context 수: {total_contexts}")

    # 배치 분할 통계
    multi_batch_tables = [
        r for r in all_results if len(r["contexts"]) > 1
    ]
    if multi_batch_tables:
        print(f"\n  다중 배치 테이블 ({len(multi_batch_tables)}개):")
        for r in multi_batch_tables:
            print(f"    - {r['table_name']}: {len(r['contexts'])}개 배치")

    # 단독 BIZ 배치 확인 (SVCImpl 없이 BIZ만 있는 배치)
    solo_biz_batches = []
    for r in all_results:
        for ctx_data in r["contexts"]:
            has_svc = any(
                extract_layer_from_path(fp) in ("SVCImpl", "SVC")
                for fp in ctx_data["file_paths"]
            )
            has_biz = any(
                extract_layer_from_path(fp) == "BIZ"
                for fp in ctx_data["file_paths"]
            )
            if has_biz and not has_svc:
                solo_biz_batches.append({
                    "table": r["table_name"],
                    "files": [Path(fp).name for fp in ctx_data["file_paths"]],
                })

    if solo_biz_batches:
        print(f"\n  !! SVCImpl 없는 단독 BIZ 배치 ({len(solo_biz_batches)}개):")
        for batch in solo_biz_batches:
            print(f"    - {batch['table']}: {', '.join(batch['files'])}")

    # 결과 저장
    if args.output:
        output_path = Path(args.output).resolve()
        save_results(all_results, output_path, logger)

    print("\n검증 완료!")


if __name__ == "__main__":
    main()
