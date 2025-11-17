# debug_files.py

import os
import sys
import pandas as pd
from collections import Counter
import tempfile  # 임시 폴더 생성을 위해 추가
import shutil    # 파일 이동 및 폴더 삭제를 위해 추가

# 제공된 debug.py 모듈을 불러옵니다.
from epsimple.debug import debug_excel, report_result
from reb.preprocess import process_excel_file

def analyze_excel_files(target_directory):
    """
    지정된 디렉토리의 모든 .xlsx 파일을 전처리하고 디버깅한 후,
    분석 결과를 요약 및 상세 보고서 CSV 파일로 저장합니다.
    (preprocess.py 파일은 수정하지 않는 방식)
    """
    print(f"\n'{target_directory}' 디렉토리에서 .xlsx 파일을 찾습니다...")

    try:
        excel_files = [f for f in os.listdir(target_directory) if f.endswith('.xlsx') and not f.startswith('~')]
    except FileNotFoundError:
        print(f"오류: '{target_directory}' 경로를 찾을 수 없습니다.")
        return

    if not excel_files:
        print("분석할 .xlsx 파일이 해당 디렉토리에 없습니다.")
        return

    summary_data = []
    all_reports = []

    # 1. 임시 디렉토리 생성
    temp_dir = tempfile.mkdtemp()
    print(f"\n임시 폴더 생성: {temp_dir}")

    try:
        print(f"총 {len(excel_files)}개의 .xlsx 파일을 분석합니다...")

        for filename in excel_files:
            full_path = os.path.join(target_directory, filename)
            print(f"- {filename} 전처리 및 분석 중...")
            
            # 전처리 후 생성될 파일의 경로를 추적하기 위한 변수
            processed_file_original_location = None
            try:
                # 2. 원본 파일 위치에서 전처리 실행
                # -> 결과물은 원본 파일과 같은 폴더에 생성됨
                processed_file_original_location = process_excel_file(
                    full_path,
                    suffix="_preprocessed"
                )

                if processed_file_original_location is None: # 전처리 중 오류 발생
                    continue
                
                # 3. 생성된 전처리 파일을 임시 폴더로 '이동'
                # shutil.move는 이동 후 새로운 경로를 반환합니다.
                processed_file_temp_location = shutil.move(
                    processed_file_original_location,
                    temp_dir
                )
                
                # 4. 임시 폴더로 이동된 파일을 디버깅
                exceptions, warnings = debug_excel(processed_file_temp_location, include_reb=True)

                # --- 요약 보고서 데이터 생성 ---
                total_errors = len(exceptions)
                total_warnings = len(warnings)
                simulation_possible = "가능" if total_errors == 0 else "불가능"
                error_counts = Counter(type(e).__name__ for e in exceptions)
                warning_counts = Counter(type(w).__name__ for w in warnings)

                summary_row = {
                    "filename": filename, # 보고서에는 원본 파일명 사용
                    "total_errors": total_errors,
                    "total_warnings": total_warnings,
                    "simulation_possible": simulation_possible,
                }
                summary_row.update({f"error_{k}": v for k, v in error_counts.items()})
                summary_row.update({f"warning_{k}": v for k, v in warning_counts.items()})
                summary_data.append(summary_row)

                # --- 상세 보고서 데이터 생성 ---
                _, report_df = report_result(exceptions, warnings)
                if not report_df.empty:
                    report_df.insert(0, "filename", filename)
                    all_reports.append(report_df)

            except Exception as e:
                print(f"  ** '{filename}' 파일 처리 중 오류 발생: {e}")
                # 만약 전처리 파일이 생성된 후 이동/디버깅 과정에서 오류가 났다면,
                # 원본 폴더에 남아있는 전처리 파일을 삭제해줍니다.
                if processed_file_original_location and os.path.exists(processed_file_original_location):
                    os.remove(processed_file_original_location)
                    print(f"  ** '{os.path.basename(processed_file_original_location)}' 정리 완료")

        # --- CSV 파일로 저장 ---
        if summary_data:
            summary_df = pd.DataFrame(summary_data).fillna(0)
            cols = ["filename", "simulation_possible", "total_errors", "total_warnings"]
            other_cols = [col for col in summary_df.columns if col not in cols]
            summary_df = summary_df[cols + sorted(other_cols)]
            summary_df.to_csv("summary_report.csv", index=False, encoding='utf-8-sig')
            print("\n'summary_report.csv' 파일이 성공적으로 저장되었습니다.")

        if all_reports:
            detailed_report_df = pd.concat(all_reports, ignore_index=True)
            detailed_report_df.to_csv("detailed_report.csv", index=False, encoding='utf-8-sig')
            print("'detailed_report.csv' 파일이 성공적으로 저장되었습니다.")
        else:
            print("\n상세 보고서에 기록할 에러나 경고가 없습니다.")

    finally:
        # 5. 작업 완료 후 임시 폴더와 그 안의 모든 파일 최종 삭제
        print(f"\n임시 폴더 삭제: {temp_dir}")
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    input_dir = r"D:\tester"
    analyze_excel_files(input_dir)