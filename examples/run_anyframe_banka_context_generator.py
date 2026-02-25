"""
AnyframeBanka Context Generator 검증 스크립트

call_stack 기반 파일 그룹핑이 올바르게 동작하는지 검증합니다.

주요 기능:
    - call_stack 기반 SVC→BIZ 그룹핑 결과 확인
    - BIZ 메서드 추출 시뮬레이션 (Phase 2 프롬프트 내용 미리보기)
    - call_stack ↔ context BIZ 매칭 검증

사용법:
    python examples/run_anyframe_banka_context_generator.py --config config.banka.json

옵션:
    --config: config.json 파일 경로 (필수)
    --table: 특정 테이블만 검증 (선택, 기본값: 전체)
    --output: 결과를 저장할 파일 경로 (선택)
    --verbose: 상세 로그 출력 (선택)
    --show-endpoints: 엔드포인트 추출 테스트 (선택)
    --log-file: 로그를 저장할 파일 경로 (선택)
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
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from modifier.context_generator.anyframe_banka_context_generator import (
    AnyframeBankaContextGenerator,
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
        logging.getLogger("applycrypto").setLevel(logging.WARNING)
        logging.getLogger("applycrypto.anyframe_context_generator").setLevel(
            logging.WARNING
        )
        logging.getLogger("applycrypto.anyframe_banka_context_generator").setLevel(
            logging.WARNING
        )
        logging.getLogger("applycrypto.context_generator").setLevel(logging.WARNING)

    if log_file:
        with open(log_file, "w", encoding="utf-8"):
            pass

        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().setLevel(logging.DEBUG)

        sys.stdout = TeeStream(sys.stdout, log_file)

    return logging.getLogger("run_anyframe_banka_context_generator")


def load_table_access_info(config: Configuration) -> List[TableAccessInfo]:
    """타겟 프로젝트의 table_access_info.json 로드"""
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
    """Mock CodeGenerator 생성 (실제 LLM 호출 없이 테스트)"""
    mock_code_generator = MagicMock()
    mock_code_generator.calculate_token_size.return_value = 100
    mock_code_generator.create_prompt.return_value = "Mock Prompt"
    return mock_code_generator


def create_context_generator(
    config: Configuration,
    mock_code_generator: MagicMock,
) -> BaseContextGenerator:
    """AnyframeBankaContextGenerator 생성"""
    return AnyframeBankaContextGenerator(config, mock_code_generator)


def run_context_generator(
    config: Configuration,
    table_access_info: TableAccessInfo,
    logger: logging.Logger,
) -> List[ModificationContext]:
    """Context Generator 실행"""
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
    """파일 경로에서 레이어 힌트 추출"""
    path_lower = file_path.lower().replace("\\", "/")
    stem = Path(file_path).stem

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


def _get_svc_pair_candidates(class_name: str) -> Set[str]:
    """SVCImpl ↔ SVC Interface 페어링 후보 (standalone 함수)"""
    candidates: Set[str] = set()
    if class_name.endswith("Impl"):
        base = class_name[:-4]
        candidates.add(base)
        candidates.add("I" + base)
    else:
        candidates.add(class_name + "Impl")
        if class_name.startswith("I") and len(class_name) > 1:
            candidates.add(class_name[1:] + "Impl")
    return candidates


def _extract_call_stacks_for_context(
    ctx: ModificationContext,
    table_info: TableAccessInfo,
) -> List[List[str]]:
    """context에 매칭되는 call_stacks를 추출합니다.

    context의 파일 클래스 이름을 기준으로,
    call_stack 시작점(첫 2개 entry)이 일치하는 것만 수집합니다.
    """
    file_class_names = {Path(fp).stem for fp in ctx.file_paths}
    raw_call_stacks: List[List[str]] = []

    for sq in table_info.sql_queries:
        for cs in sq.get("call_stacks", []):
            if not isinstance(cs, list) or not cs:
                continue

            matches = False
            for entry in cs[:2]:
                if not isinstance(entry, str) or "." not in entry:
                    continue
                entry_class = entry.split(".")[0]

                if entry_class in file_class_names:
                    matches = True
                    break

                pair_candidates = _get_svc_pair_candidates(entry_class)
                if pair_candidates & file_class_names:
                    matches = True
                    break

            if matches and cs not in raw_call_stacks:
                raw_call_stacks.append(cs)

    return raw_call_stacks


def print_contexts(
    contexts: List[ModificationContext],
    table_info: TableAccessInfo,
    logger: logging.Logger,
):
    """컨텍스트별 통합 정보 출력

    각 context에 대해 한 곳에서 모든 정보를 보여줍니다:
    - 수정 대상 파일 (BIZ는 추출 메서드 포함)
    - VO 파일 이름
    - 매칭된 call_stacks
    - call_stack ↔ BIZ 매칭 검증
    """
    from parser.java_ast_parser import JavaASTParser

    java_parser = JavaASTParser()

    print(f"\n생성된 Context 수: {len(contexts)}")

    all_match_ok = True

    for ctx_idx, ctx in enumerate(contexts, 1):
        file_class_names = {Path(fp).stem for fp in ctx.file_paths}

        # anchor SVC 이름
        anchor_name = "unknown"
        for fp in ctx.file_paths:
            stem = Path(fp).stem
            if stem.endswith("SVCImpl") or stem.endswith("SVC"):
                anchor_name = stem
                break

        # 이 context에 매칭되는 call_stacks
        raw_call_stacks = _extract_call_stacks_for_context(ctx, table_info)

        vo_count = len(ctx.context_files) if ctx.context_files else 0

        print(f"\n{'─' * 60}")
        print(
            f"[Context {ctx_idx}] {anchor_name} "
            f"(파일 {len(ctx.file_paths)}개, VO {vo_count}개)"
        )
        print(f"{'─' * 60}")

        # ── 수정 대상 파일 + BIZ 메서드 시뮬레이션 ──
        print("  수정 대상 파일:")
        for fp in ctx.file_paths:
            filename = Path(fp).name
            stem = Path(fp).stem
            is_biz = stem.endswith("BIZ")

            if not is_biz:
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        line_count = sum(1 for _ in f)
                    print(f"    {filename} (전체, {line_count}라인)")
                except Exception:
                    print(f"    {filename} (전체)")
                continue

            # BIZ 파일: call_stack 기반 메서드 추출 시뮬레이션
            target_methods: Set[str] = set()
            for cs in raw_call_stacks:
                for sig in cs:
                    if "." in sig:
                        cls, method = sig.split(".", 1)
                        if cls == stem:
                            target_methods.add(method)

            if not target_methods:
                print(f"    {filename} (전체 — call_stack 메서드 없음)")
                continue

            try:
                tree, error = java_parser.parse_file(Path(fp))
                if error:
                    print(f"    {filename} (전체 — 파싱 실패)")
                    continue

                classes = java_parser.extract_class_info(tree, Path(fp))
                method_ranges = []
                for cls_info in classes:
                    for method in cls_info.methods:
                        if method.name in target_methods:
                            method_ranges.append(
                                (method.name, method.line_number, method.end_line_number)
                            )

                if not method_ranges:
                    print(f"    {filename} (전체 — AST 매칭 실패)")
                    continue

                with open(fp, "r", encoding="utf-8") as f:
                    full_lines = sum(1 for _ in f)
                total_method_lines = sum(
                    end - start + 1 for _, start, end in method_ranges
                )
                pct = total_method_lines / full_lines * 100 if full_lines else 0

                print(
                    f"    {filename} "
                    f"(메서드 {len(method_ranges)}개, "
                    f"{total_method_lines}/{full_lines}라인, {pct:.0f}%)"
                )
                for name, start, end in sorted(method_ranges, key=lambda x: x[1]):
                    print(f"      - {name}() (lines {start}-{end})")

            except Exception as e:
                print(f"    {filename} (처리 실패: {e})")

        # ── VO 파일 이름 ──
        if ctx.context_files:
            vo_names = [Path(fp).name for fp in ctx.context_files]
            if len(vo_names) <= 5:
                print(f"  VO: {', '.join(vo_names)}")
            else:
                print(f"  VO: {', '.join(vo_names[:5])} 외 {len(vo_names) - 5}개")

        # ── 매칭된 call_stacks ──
        if raw_call_stacks:
            print(f"  call_stacks ({len(raw_call_stacks)}개):")
            for cs in raw_call_stacks:
                print(f"    {' → '.join(cs)}")

        # ── call_stack ↔ BIZ 매칭 검증 ──
        actual_biz = {s for s in file_class_names if s.endswith("BIZ")}
        expected_biz: Set[str] = set()
        for cs in raw_call_stacks:
            for entry in cs:
                if isinstance(entry, str) and "." in entry:
                    cls = entry.split(".")[0]
                    if cls.endswith("BIZ"):
                        expected_biz.add(cls)

        missing_biz = expected_biz - actual_biz
        extra_biz = actual_biz - expected_biz

        if missing_biz or extra_biz:
            all_match_ok = False
            if missing_biz:
                print(f"  ✗ call_stack BIZ 누락: {', '.join(sorted(missing_biz))}")
            if extra_biz:
                print(f"  ⚠ 예상 외 BIZ: {', '.join(sorted(extra_biz))}")
        elif expected_biz:
            print("  ✓ call_stack ↔ BIZ 매칭 정상")

    if all_match_ok:
        print("\n✓ 모든 context의 call_stack ↔ BIZ 매칭 정상")
    else:
        print("\n✗ 매칭 불일치 발견")


def print_call_stacks_summary(
    table_info: TableAccessInfo,
    logger: logging.Logger,
):
    """call_stacks 요약 출력"""
    biz_methods: Dict[str, Set[str]] = {}

    for sq in table_info.sql_queries:
        for cs in sq.get("call_stacks", []):
            if not isinstance(cs, list):
                continue
            for entry in cs:
                if isinstance(entry, str) and "." in entry:
                    cls_name, method_name = entry.split(".", 1)
                    if cls_name.endswith("BIZ"):
                        if cls_name not in biz_methods:
                            biz_methods[cls_name] = set()
                        biz_methods[cls_name].add(method_name)

    if biz_methods:
        print("\n  call_stack에 등장하는 BIZ 클래스 및 메서드:")
        for cls_name, methods in sorted(biz_methods.items()):
            print(f"    {cls_name}: {', '.join(sorted(methods))}")

    # call_stack 시작점 클래스
    start_classes: Set[str] = set()
    for sq in table_info.sql_queries:
        for cs in sq.get("call_stacks", []):
            if isinstance(cs, list) and cs:
                first = cs[0]
                if isinstance(first, str) and "." in first:
                    start_classes.add(first.split(".")[0])
    if start_classes:
        print(f"  call_stack 시작점 클래스: {', '.join(sorted(start_classes))}")


def print_call_stacks_detail(
    table_info: TableAccessInfo,
    logger: logging.Logger,
):
    """call_stack 전체 체인을 출력합니다."""
    print("\n  === call_stack 전체 체인 ===")
    idx = 0
    for sq in table_info.sql_queries:
        for cs in sq.get("call_stacks", []):
            if not isinstance(cs, list) or not cs:
                continue
            idx += 1
            chain_str = " → ".join(cs)
            print(f"  [{idx}] {chain_str}")
    if idx == 0:
        print("  (call_stack 없음)")


def run_endpoint_extraction(
    config: Configuration,
    table_info: TableAccessInfo,
    logger: logging.Logger,
):
    """엔드포인트 추출 테스트"""
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

    svc_files = table_info.layer_files.get("svc", [])
    if not svc_files:
        print("  SVC 파일이 없습니다.")
        return

    total_endpoints = 0
    for svc_file in svc_files[:10]:
        try:
            tree, error = java_parser.parse_file(Path(svc_file))
            if error:
                continue

            classes = java_parser.extract_class_info(tree, Path(svc_file))
            endpoints = strategy.extract_endpoints_from_classes(classes)

            if endpoints:
                total_endpoints += len(endpoints)
                for ep in endpoints:
                    print(
                        f"  [{Path(svc_file).name}] "
                        f"{ep.method_signature} → {ep.path or '(no path)'}"
                    )
        except Exception as e:
            logger.debug(f"엔드포인트 추출 실패: {Path(svc_file).name} - {e}")

    print(
        f"\n  총 엔드포인트: {total_endpoints}개 "
        f"(SVC {min(len(svc_files), 10)}개 검사)"
    )


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
        description="AnyframeBanka Context Generator 검증 스크립트 "
        "(call_stack 기반 그룹핑)"
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

        if not table_info.layer_files:
            logger.warning(
                f"테이블 '{table_info.table_name}'에 layer_files가 없습니다. 스킵합니다."
            )
            continue

        # 테이블 헤더
        print(f"\n{'=' * 70}")
        print(f"테이블: {table_info.table_name}")
        print(f"{'=' * 70}")

        # call_stacks 요약
        print_call_stacks_summary(table_info, logger)

        # call_stack 전체 체인 (verbose에서만)
        if args.verbose:
            print_call_stacks_detail(table_info, logger)

        # Context 생성
        try:
            contexts = run_context_generator(config, table_info, logger)
        except Exception as e:
            logger.error(f"Context 생성 실패: {e}")
            import traceback

            traceback.print_exc()
            continue

        # 통합 출력 (파일 목록 + BIZ 메서드 + call_stack 매칭)
        print_contexts(contexts, table_info, logger)

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
                    "file_count": ctx.file_count,
                    "file_paths": ctx.file_paths,
                    "context_files": ctx.context_files or [],
                }
                for ctx in contexts
            ],
        }
        all_results.append(table_result)

    # 전체 요약
    print(f"\n{'=' * 70}")
    print("전체 요약")
    print(f"{'=' * 70}")
    print(f"처리된 테이블 수: {len(all_results)}")
    total_contexts = sum(len(r["contexts"]) for r in all_results)
    print(f"생성된 총 Context 수: {total_contexts}")

    # 배치 분할 통계
    multi_batch_tables = [r for r in all_results if len(r["contexts"]) > 1]
    if multi_batch_tables:
        print(f"\n  다중 배치 테이블 ({len(multi_batch_tables)}개):")
        for r in multi_batch_tables:
            print(f"    - {r['table_name']}: {len(r['contexts'])}개 배치")

    # 결과 저장
    if args.output:
        output_path = Path(args.output).resolve()
        save_results(all_results, output_path, logger)

    print("\n검증 완료!")


if __name__ == "__main__":
    main()
