"""Mini NPU Simulator
- 모드 1: 3x3 필터 2개(A, B)와 패턴을 직접 입력받아 MAC 점수로 판정
- 모드 2: data.json의 필터/패턴을 일괄 분석하고 expected와 비교(PASS/FAIL)
- 보너스 3: 2차원 vs 1차원(평탄화) MAC 성능 비교 / 보너스 4: N x N 패턴 생성기
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


def measure_ms(pattern, filt, repeat=REPEAT, fn=mac):
    """fn(기본 mac)을 repeat번 호출한 평균 시간(ms). 입출력은 측정 구간 밖."""
    start = time.perf_counter()
    for _ in range(repeat):
        fn(pattern, filt)
    end = time.perf_counter()
    return (end - start) / repeat * 1000


def make_cross(n):
    """[보너스] N x N 십자가 패턴: 가운데 행과 가운데 열을 1.0으로 채운다. (홀수 N 권장)"""
    mid = n // 2
    return [[1.0 if (i == mid or j == mid) else 0.0 for j in range(n)] for i in range(n)]


def make_x(n):
    """[보너스] N x N X 패턴: 두 대각선을 1.0으로 채운다."""
    return [[1.0 if (i == j or i + j == n - 1) else 0.0 for j in range(n)] for i in range(n)]


def flatten(m):
    """[보너스] N x N 2차원 배열 -> 길이 N^2 의 1차원 배열 (칸 (i, j) -> 인덱스 i*N + j)."""
    return [v for row in m for v in row]


def mac_flat(pattern_flat, filter_flat):
    """[보너스] 1차원 배열 버전 MAC: 이중 루프 대신 단일 루프로 접근한다."""
    total = 0.0
    for k in range(len(pattern_flat)):
        total += pattern_flat[k] * filter_flat[k]
    return total


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

    show_mac_result(pattern, filter_a, filter_b, "A", "B",
                    f"판정 불가 (|A-B| < {EPSILON:g})")


def show_mac_result(pattern, filt_a, filt_b, label_a, label_b, undecided):
    """MAC 점수 / 연산 시간 / 판정 / 성능 표를 출력한다. (모드 1과 패턴 생성기가 함께 사용)"""
    n = len(pattern)
    score_a = mac(pattern, filt_a)
    score_b = mac(pattern, filt_b)
    avg_ms = measure_ms(pattern, filt_a)       # 10회 평균
    result = judge(score_a, score_b, label_a, label_b, undecided)

    print("\n#----------------------------------------")
    print("# [3] MAC 결과")
    print("#----------------------------------------")
    print(f"{label_a} 점수: {score_a}")
    print(f"{label_b} 점수: {score_b}")
    print(f"연산 시간(평균/{REPEAT}회): {avg_ms:.4f} ms")
    print(f"판정: {result}")

    print("\n#----------------------------------------")
    print(f"# [4] 성능 분석 ({n}x{n})")
    print("#----------------------------------------")
    print_perf_table([n])


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
        p, f = make_cross(n), make_x(n)
        avg = measure_ms(p, f)
        print(f"{f'{n}x{n}':<10}{avg:<16.6f}{n * n:<10}")


# ------------------------------------------------------------
# 보너스
# ------------------------------------------------------------
def run_bonus_compare():
    """[보너스 3] 2차원 mac vs 1차원 mac_flat: 동일 입력, 동일 반복 횟수(10회 평균)로 비교."""
    print("\n#----------------------------------------")
    print(f"# [보너스] 2차원 vs 1차원 배열 MAC 성능 비교 (평균/{REPEAT}회)")
    print("#----------------------------------------")
    print(f"{'크기':<10}{'2차원(ms)':<14}{'1차원(ms)':<14}{'개선(배)':<10}{'점수 일치'}")
    print("-" * 56)
    for n in PERF_SIZES:
        p2, f2 = make_cross(n), make_x(n)           # 동일 입력
        p1, f1 = flatten(p2), flatten(f2)           # 평탄화는 측정 구간 밖
        same = abs(mac(p2, f2) - mac_flat(p1, f1)) < EPSILON
        t2 = measure_ms(p2, f2, REPEAT, mac)
        t1 = measure_ms(p1, f1, REPEAT, mac_flat)
        ratio = t2 / t1 if t1 > 0 else float("inf")
        print(f"{f'{n}x{n}':<10}{t2:<14.6f}{t1:<14.6f}{ratio:<10.2f}{'OK' if same else 'NG'}")


def read_int(prompt, low=1, high=99):
    while True:
        raw = input(prompt).strip()
        try:
            v = int(raw)
        except ValueError:
            print("정수를 입력하세요.")
            continue
        if low <= v <= high:
            return v
        print(f"{low} 이상 {high} 이하의 정수를 입력하세요.")


def print_grid(m):
    for row in m:
        print(" ".join(str(int(v)) for v in row))


def run_bonus_generator():
    """[보너스 4] N을 입력하면 Cross/X 패턴을 생성하고, 생성된 패턴을 MAC 판정에 재활용한다."""
    n = read_int("패턴 크기 N 입력 (1~99, 홀수 권장): ")
    cross, x = make_cross(n), make_x(n)
    print(f"\n[생성된 Cross {n}x{n}]")
    print_grid(cross)
    print(f"\n[생성된 X {n}x{n}]")
    print_grid(x)

    pick = read_int("\n판정에 사용할 패턴 선택 (1: Cross, 2: X): ", 1, 2)
    pattern = cross if pick == 1 else x
    print(f"\n→ 필터 A=Cross, 필터 B=X 로 {'Cross' if pick == 1 else 'X'} 패턴을 판정합니다.")
    show_mac_result(pattern, cross, x, "Cross", "X", f"판정 불가 (|차이| < {EPSILON:g})")


# ------------------------------------------------------------
def main():
    print("=== Mini NPU Simulator ===\n")
    print("[모드 선택]\n")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    print("3. [보너스] 2차원 vs 1차원 배열 성능 비교")
    print("4. [보너스] 패턴 생성기 (N x N)")
    while True:
        choice = input("선택: ").strip()
        if choice == "1":
            run_mode1()
            break
        if choice == "2":
            run_mode2()
            break
        if choice == "3":
            run_bonus_compare()
            break
        if choice == "4":
            run_bonus_generator()
            break
        print("1~4 중에서 입력하세요.")


if __name__ == "__main__":
    main()