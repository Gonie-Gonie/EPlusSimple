import os
import argparse
from pathlib import Path

# local modules (idragon 패키지가 설치되거나 경로에 있다고 가정)
from idragon import read_idd

def batch_convert_idd_to_pickle(source_dir: str, verbose: bool = True):
    """
    지정된 폴더 내의 IDD 파일들을 읽어 pickle 파일로 일괄 변환하여 저장합니다.
    """
    src = Path(source_dir).resolve()
    
    if not src.exists() or not src.is_dir():
        print(f"[오류] 유효하지 않은 폴더 경로입니다: {src}")
        return

    # 안전성을 위해 .idd 확장자를 가진 파일만 필터링
    idd_files = [f for f in src.iterdir() if f.is_file() and f.suffix.lower() == '.idd']
    
    if not idd_files:
        print(f"[안내] '{src}' 폴더 내에 .idd 파일이 없습니다.")
        return

    # 원본 코드처럼 역순([::-1])으로 처리하고 싶다면 sorted 활용 가능
    # idd_files = sorted(idd_files, reverse=True) 
    
    count = 0
    for file_path in idd_files:
        try:
            if verbose:
                print(f"\n[진행] {file_path.name} 변환 시작...")
                
            # IDD 읽기
            idd = read_idd(str(file_path), verbose=verbose)
            
            # Pickle로 저장 (원본 스크립트와 동일하게 원본 폴더 경로에 저장)
            idd.to_pickle(str(src))
            count += 1
            
        except Exception as e:
            print(f"[오류] {file_path.name} 처리 중 문제 발생: {e}")

    print(f"\n✅ 완료: 총 {count}개의 IDD 파일이 Pickle로 성공적으로 변환되었습니다.")


def parse_arguments():
    """명령줄 인수(CLI Arguments)를 파싱하는 함수"""
    parser = argparse.ArgumentParser(
        description="폴더 내의 IDD 파일들을 읽어 Pickle 형식으로 일괄 변환합니다.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # 필수 입력: source_dir
    parser.add_argument("source_dir", type=str, help="IDD 파일들이 위치한 대상 폴더 경로")
    
    # 선택 입력: 로깅 관련
    parser.add_argument("-q", "--quiet", action="store_true", help="진행 상황 출력(Verbose) 끄기")

    return parser.parse_args()


# ============================================================================ #
#                                    MAIN                                      #
# ============================================================================ #

if __name__ == "__main__":
    """
    [스크립트 사용법]
    터미널(CMD)에서 아래와 같이 실행합니다.
    
    1. 기본 실행 (경로만 입력):
       python convert_idd.py "B:\\공유 드라이브\\...\\idd_generation"
       
    2. 조용히 실행 (Verbose 끄기):
       python convert_idd.py "경로" -q
    """
    
    args = parse_arguments()

    # 옵션에 따라 verbose 상태 결정 (quiet가 True면 verbose는 False)
    is_verbose = not args.quiet

    batch_convert_idd_to_pickle(
        source_dir=args.source_dir,
        verbose=is_verbose
    )