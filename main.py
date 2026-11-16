"""Mini NPU Simulator
- 모드 1: 3x3 필터 2개(A, B)와 패턴을 직접 입력받아 MAC 점수로 판정
- 모드 2: data.json의 필터/패턴을 일괄 분석하고 expected와 비교(PASS/FAIL)
- 외부 라이브러리 없이 표준 라이브러리(json, time, os, re)만 사용
"""
import json
import os
import re
import time

EPSILON = 1e-9          # 점수 비교 허용오차 (|a-b| < EPSILON 이면 동점)
REPEAT = 10             # 성능 측정 반복 횟수
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
PERF_SIZES = [3, 5, 13, 25]

# 표준 라벨은 Cross, X 두 가지. 입력 표기는 모두 소문자로 바꿔 이 표에서 찾는다.
LABEL_MAP = {"+": "Cross", "cross": "Cross", "x": "X"}


# ------------------------------------------------------------
# 핵심 로직
# ------------------------------------------------------------
def normalize_label(raw):
    """'+', 'cross', 'x' 등 다양한 표기를 표준 라벨(Cross / X)로 통일한다."""
    if not isinstance(raw, str):
        raise ValueError(f"라벨이 문자열이 아님: {raw!r}")
    key = raw.strip().lower()
    if key not in LABEL_MAP:
        raise ValueError(f"알 수 없는 라벨: {raw!r}")
    return LABEL_MAP[key]


def mac(pattern, filt):
    """MAC 연산: 같은 위치끼리 곱해서 전부 더한다. (반복문 직접 구현, I/O 없음)"""
    n = len(pattern)
    total = 0.0
    for i in range(n):
        for j in range(n):
            total += pattern[i][j] * filt[i][j]
    return total


def judge(score_a, score_b, label_a, label_b, undecided):
    """두 점수를 epsilon 기준으로 비교해 라벨을 반환한다. 동점이면 undecided 문구."""
    if abs(score_a - score_b) < EPSILON:
        return undecided
    return label_a if score_a > score_b else label_b


def measure_ms(pattern, filt, repeat=REPEAT):
    """mac()을 repeat번 호출한 평균 시간(ms). 입출력은 측정 구간 밖."""
    start = time.perf_counter()
    for _ in range(repeat):
        mac(pattern, filt)
    end = time.perf_counter()
    return (end - start) / repeat * 1000


def make_dummy(n):
    """성능 측정용 N x N 더미 행렬 (전부 1.0)."""
    return [[1.0] * n for _ in range(n)]


# ------------------------------------------------------------
# 모드 1: 사용자 입력 (3x3)
# ------------------------------------------------------------
def read_matrix(title, n=3):
    """n줄을 입력받는다. 형식이 틀리면 안내 후 처음부터 다시 입력받는다."""
    while True:
        print(f"{title} ({n}줄 입력, 공백 구분)")
        rows = []
        ok = True
        for _ in range(n):
            parts = input().split()
            if len(parts) != n:
                print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요.")
                ok = False
                break
            try:
                rows.append([float(p) for p in parts])
            except ValueError:
                print("입력 형식 오류: 숫자만 입력할 수 있습니다.")
                ok = False
                break
        if ok:
            return rows


def run_mode1():
    print("\n#----------------------------------------")
    print("# [1] 필터 입력")
    print("#----------------------------------------")
    filter_a = read_matrix("필터 A")
    print()
    filter_b = read_matrix("필터 B")
    print("\n✓ 필터 A, B 저장 완료")

    print("\n#----------------------------------------")
    print("# [2] 패턴 입력")
    print("#----------------------------------------")
    pattern = read_matrix("패턴")

    score_a = mac(pattern, filter_a)
    score_b = mac(pattern, filter_b)
    # 성능: A 필터와의 MAC 1회를 10번 반복한 평균
    avg_ms = measure_ms(pattern, filter_a)
    result = judge(score_a, score_b, "A", "B", f"판정 불가 (|A-B| < {EPSILON:g})")

    print("\n#----------------------------------------")
    print("# [3] MAC 결과")
    print("#----------------------------------------")
    print(f"A 점수: {score_a}")
    print(f"B 점수: {score_b}")
    print(f"연산 시간(평균/{REPEAT}회): {avg_ms:.4f} ms")
    print(f"판정: {result}")

    print("\n#----------------------------------------")
    print("# [4] 성능 분석 (3x3)")
    print("#----------------------------------------")
    print_perf_table([3])


# ------------------------------------------------------------
# 모드 2: data.json 분석
# ------------------------------------------------------------
def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_matrix(m, n, name):
    """m이 숫자로 된 n x n 2차원 리스트인지 검사. 문제가 있으면 ValueError."""
    if not isinstance(m, list) or len(m) != n:
        rows = len(m) if isinstance(m, list) else "?"
        raise ValueError(f"{name} 행 수 불일치 (기대 {n}, 실제 {rows})")
    for r, row in enumerate(m):
        if not isinstance(row, list) or len(row) != n:
            cols = len(row) if isinstance(row, list) else "?"
            raise ValueError(f"{name} {r}행 열 수 불일치 (기대 {n}, 실제 {cols})")
        if not all(is_number(v) for v in row):
            raise ValueError(f"{name} {r}행에 숫자가 아닌 값이 있음")


def load_filters(raw_filters):
    """filters를 {N: {'Cross': 행렬, 'X': 행렬}} 형태로 정리한다. 라벨 정규화 포함."""
    result = {}
    for size_key, group in raw_filters.items():
        try:
            m = re.fullmatch(r"size_(\d+)", size_key)
            if not m:
                raise ValueError("키 형식이 size_N 이 아님")
            n = int(m.group(1))
            std = {}
            for raw_label, matrix in group.items():
                label = normalize_label(raw_label)
                validate_matrix(matrix, n, f"{size_key}/{raw_label}")
                std[label] = matrix
            if set(std) != {"Cross", "X"}:
                raise ValueError("Cross, X 필터가 모두 있어야 함")
            result[n] = std
            print(f"✓ {size_key:<8} 필터 로드 완료 (Cross, X)")
        except (ValueError, AttributeError) as e:
            print(f"✗ {size_key:<8} 필터 로드 실패: {e}")
    return result


def analyze_case(case_id, case, filters):
    """패턴 1개를 분석해 (결과 dict) 반환. 문제가 생기면 ValueError를 던진다."""
    m = re.fullmatch(r"size_(\d+)_\d+", case_id)
    if not m:
        raise ValueError("패턴 키 형식이 size_N_idx 가 아님")
    n = int(m.group(1))
    if n not in filters:
        raise ValueError(f"size_{n} 필터가 없거나 로드에 실패함")
    if not isinstance(case, dict) or "input" not in case or "expected" not in case:
        raise ValueError("input/expected 키가 없음")

    expected = normalize_label(case["expected"])
    validate_matrix(case["input"], n, "패턴")   # 패턴 크기 = N 인지 검사
    # 필터 크기는 load_filters에서 이미 N x N 으로 검증됨

    s_cross = mac(case["input"], filters[n]["Cross"])
    s_x = mac(case["input"], filters[n]["X"])
    verdict = judge(s_cross, s_x, "Cross", "X", "UNDECIDED")
    return {"cross": s_cross, "x": s_x, "verdict": verdict, "expected": expected}


def run_mode2():
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        raw_filters, raw_patterns = data["filters"], data["patterns"]
    except FileNotFoundError:
        print(f"data.json 을 찾을 수 없습니다: {DATA_PATH}")
        return
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"data.json 형식 오류: {e!r}")
        return

    print("\n#----------------------------------------")
    print("# [1] 필터 로드")
    print("#----------------------------------------")
    filters = load_filters(raw_filters)

    print("\n#----------------------------------------")
    print("# [2] 패턴 분석 (라벨 정규화 적용)")
    print("#----------------------------------------")
    total, passed, failures = 0, 0, []
    for case_id, case in raw_patterns.items():
        total += 1
        print(f"--- {case_id} ---")
        try:
            r = analyze_case(case_id, case, filters)
        except ValueError as e:          # 스키마/크기/라벨 문제 -> 케이스 단위 FAIL
            print(f"판정: 불가 | FAIL ({e})")
            failures.append((case_id, str(e)))
            continue

        print(f"Cross 점수: {r['cross']}")
        print(f"X 점수: {r['x']}")
        if r["verdict"] == r["expected"]:
            passed += 1
            print(f"판정: {r['verdict']} | expected: {r['expected']} | PASS")
        else:
            if r["verdict"] == "UNDECIDED":
                reason = "동점(UNDECIDED) 처리 규칙에 따라 FAIL"
            else:
                reason = f"판정 {r['verdict']} != expected {r['expected']}"
            failures.append((case_id, reason))
            print(f"판정: {r['verdict']} | expected: {r['expected']} | FAIL ({reason})")

    print("\n#----------------------------------------")
    print(f"# [3] 성능 분석 (평균/{REPEAT}회)")
    print("#----------------------------------------")
    print_perf_table(PERF_SIZES)

    print("\n#----------------------------------------")
    print("# [4] 결과 요약")
    print("#----------------------------------------")
    print(f"총 테스트: {total}개")
    print(f"통과: {passed}개")
    print(f"실패: {len(failures)}개")
    if failures:
        print("\n실패 케이스:")
        for cid, reason in failures:
            print(f"- {cid}: {reason}")
    print('\n(상세 원인 분석 및 복잡도 설명은 README.md의 "결과 리포트" 섹션 참고)')


# ------------------------------------------------------------
# 성능 표
# ------------------------------------------------------------
def print_perf_table(sizes):
    print(f"{'크기':<10}{'평균 시간(ms)':<16}{'연산 횟수(N²)':<10}")
    print("-" * 38)
    for n in sizes:
        p, f = make_dummy(n), make_dummy(n)
        avg = measure_ms(p, f)
        print(f"{f'{n}x{n}':<10}{avg:<16.6f}{n * n:<10}")


# ------------------------------------------------------------
def main():
    print("=== Mini NPU Simulator ===\n")
    print("[모드 선택]\n")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    while True:
        choice = input("선택: ").strip()
        if choice == "1":
            run_mode1()
            break
        if choice == "2":
            run_mode2()
            break
        print("1 또는 2를 입력하세요.")


if __name__ == "__main__":
    main()