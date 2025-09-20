# ==============================================================================
# 1. 모듈 임포트 및 전역 설정
# ==============================================================================

# built-in modules
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import argparse

# third-party modules
import pandas as pd
from flask import Flask, render_template, request
from werkzeug.datastructures import FileStorage

# local modules
from pyGRsim import check_grexcel, run_grexcel
from pyGRsim.reb.preprocess import process_excel_file
from pyGRsim.debug import debug_excel, report_result, ReportCode

# ==============================================================================
# 2. Flask 앱 및 환경 설정
# ==============================================================================

# 업로드 폴더를 현재 파일 위치 기준으로 'uploads' 폴더로 지정
UPLOAD_FOLDER = Path(__file__).parent / "uploads"
# 업로드 폴더가 없으면 생성
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Flask 앱 인스턴스 생성 및 설정
app = Flask(__name__, template_folder="./templates")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["JSON_AS_ASCII"] = False # 한글 깨짐 방지


# ==============================================================================
# 3. 공용 헬퍼 함수
# ==============================================================================

def handle_file_processing(
    file: Optional[FileStorage],
    handler_func: callable,
    failure_response: Dict[str, Any],
    **kwargs: Any,
) -> Any:
    """
    단일 파일 업로드를 안전하게 처리하고 지정된 핸들러 함수를 실행합니다.

    파일을 임시 폴더에 저장하고 핸들러 함수를 호출한 뒤, 성공/실패 여부와 관계없이
    파일을 삭제하여 서버에 불필요한 파일이 남지 않도록 합니다.

    Args:
        file: Flask request에서 받은 파일 스토리지 객체.
        handler_func: 저장된 파일 경로를 인자로 받아 처리할 함수(예: check_grexcel).
        failure_response: 파일이 없거나 이름이 없을 경우 반환할 딕셔너리.
        **kwargs: handler_func에 전달할 추가 인자.

    Returns:
        handler_func의 실행 결과 또는 실패 응답 딕셔너리.
    """
    if not file or not file.filename:
        return failure_response

    # 파일 경로를 pathlib.Path 객체로 관리
    filepath = UPLOAD_FOLDER / file.filename
    try:
        file.save(filepath)
        result = handler_func(str(filepath), **kwargs)
    finally:
        # 파일 처리 후 반드시 삭제
        if filepath.exists():
            filepath.unlink()
    return result


# ==============================================================================
# 4. 라우트 (웹페이지 기능)
# ==============================================================================

@app.route("/check", methods=["GET", "POST"])
def check_file_validity() -> str:
    """
    '유효성 검증' 페이지를 렌더링하고, POST 요청 시 업로드된 엑셀 파일의
    포맷을 검증하여 결과를 표시합니다.
    """
    result: Optional[Dict[str, Any]] = None
    if request.method == "POST":
        uploaded_file = request.files.get("file")
        
        # 파일이 업로드되지 않았을 때의 기본 응답
        fail_dict = {
            "step1": False, "step2": False, "step3": False, "step4": False,
            "err": "파일이 업로드되지 않았습니다.",
        }
        
        result = handle_file_processing(uploaded_file, check_grexcel, fail_dict)
        
    return render_template("check.html", result=result)


@app.route("/run", methods=["GET", "POST"])
def run_simulation_comparison() -> str:
    """
    '비교 분석' 페이지를 렌더링하고, POST 요청 시 다음 로직에 따라 시뮬레이션을 실행합니다.

    1. **파일 저장**: '리모델링 전' 파일과 '리모델링 후' 파일(들)을 임시 저장합니다.
    2. **[수정] 선행 전처리**: '전처리' 옵션이 선택된 경우, 저장된 모든 파일에 대해 전처리를 먼저 수행합니다.
    3. **대상 파일 디버깅**: 전처리된 파일(또는 원본 파일)에 대해 `debug_excel`을 실행하여 오류를 확인합니다.
    4. **오류 분기**:
        - 'SEVERE' 오류가 발견되면, 시뮬레이션을 중단하고 오류 보고서만 표시합니다.
        - 오류가 없으면, 경고 보고서와 함께 시뮬레이션 결과를 모두 표시합니다.
    5. **파일 정리**: 작업 완료 후 원본 및 전처리된 모든 임시 파일을 삭제합니다.
    """
    result: Optional[Dict[str, Any]] = None
    # 임시 저장된 원본 파일 경로들을 관리 (key: 원본 파일명, value: Path 객체)
    saved_filepaths: Dict[str, Path] = {}
    # 전처리 후 생성된 파일 경로들을 관리 (정리용)
    preprocessed_filepaths: List[Path] = []

    if request.method == "POST":
        try:
            # 1. 사용자 입력 및 파일 가져오기
            preprocess_needed = request.form.get("preprocess") == "true"
            file_before = request.files.get("file_before")
            files_after = request.files.getlist("file_after")

            if not file_before or not file_before.filename:
                return render_template("run.html", result={"err": "'리모델링 전' 파일이 선택되지 않았습니다."})
            
            all_files = [file_before] + [f for f in files_after if f.filename]
            
            # 2. 모든 원본 파일 임시 저장
            for file_obj in all_files:
                if file_obj.filename:
                    filepath = UPLOAD_FOLDER / file_obj.filename
                    file_obj.save(filepath)
                    file_obj.seek(0)
                    saved_filepaths[file_obj.filename] = filepath
            
            # 3. [수정] 전처리 옵션에 따라 디버깅 및 실행할 '대상 파일' 결정
            target_filepaths: Dict[str, Path] = {}
            if preprocess_needed:
                for filename, original_path in saved_filepaths.items():
                    # 전처리를 실행하고 생성된 새 파일의 경로를 저장
                    preprocessed_path_str = process_excel_file(str(original_path))
                    preprocessed_path = Path(preprocessed_path_str)
                    target_filepaths[filename] = preprocessed_path
                    preprocessed_filepaths.append(preprocessed_path) # 정리 목록에 추가
            else:
                # 전처리가 필요 없으면 원본 파일을 대상으로 지정
                target_filepaths = saved_filepaths

            # 4. [수정] 대상 파일(전처리됐거나 원본)에 대해 디버깅 실행
            debug_reports, has_severe_error, final_report_df = _run_debugging_phase(target_filepaths)
            
            # 5. CSV 데이터 생성
            csv_data = None
            if final_report_df is not None and not final_report_df.empty:
                csv_data = final_report_df.to_csv(index=False, encoding='utf-8-sig')

            # 6. 분기: SEVERE 오류 여부에 따라 시뮬레이션 실행 또는 중단
            if has_severe_error:
                result = {
                    "err": "심각한 오류가 발견되어 시뮬레이션을 취소했습니다. 아래 보고서를 확인해주세요.",
                    "debug_reports": debug_reports,
                    "csv_data": csv_data,
                }
            else:
                # SEVERE 오류가 없을 경우 시뮬레이션 실행 (디버깅을 통과한 대상 파일 사용)
                sim_data = _run_simulation_phase(
                    target_filepaths, # [수정]
                    file_before.filename,
                    [f.filename for f in files_after if f.filename]
                )
                
                result = {
                    "debug_reports": [
                        report for report in debug_reports if report.get("warning_html")
                    ],
                    "csv_data": csv_data,
                    "sim_data": sim_data
                }

        finally:
            # 7. [수정] 모든 임시 파일(원본 + 전처리된 파일) 정리
            all_files_to_delete = list(saved_filepaths.values()) + preprocessed_filepaths
            deleted_count = 0
            for path in all_files_to_delete:
                if path.exists():
                    path.unlink()
                    deleted_count += 1
            print(f"임시 파일 {deleted_count}개 정리 완료")
            
    return render_template("run.html", result=result)


def _run_debugging_phase(
    filepaths: Dict[str, Path]
) -> Tuple[List[Dict[str, Any]], bool, Optional[pd.DataFrame]]:
    """
    지정된 모든 파일 경로에 대해 디버깅을 수행하고 결과를 집계합니다.

    Args:
        filepaths: 파일명을 key로, 파일의 Path 객체를 value로 갖는 딕셔너리.

    Returns:
        - debug_reports (List): 각 파일의 디버그 결과를 담은 딕셔너리 리스트.
        - has_severe_error (bool): 'SEVERE' 등급의 오류가 있었는지 여부.
        - final_report_df (pd.DataFrame): 모든 보고서를 병합한 단일 데이터프레임.
    """
    debug_reports: List[Dict[str, Any]] = []
    all_report_dfs: List[pd.DataFrame] = []
    has_severe_error = False

    for filename, path in filepaths.items():
        exceptions, warnings = debug_excel(str(path))
        code, report_df = report_result(exceptions, warnings)
        
        if code == ReportCode.SEVERE:
            has_severe_error = True
            
        report_data: Dict[str, Any] = {"filename": filename, "code": code.name}
        severe_html, warning_html = None, None
        
        if not report_df.empty:
            # CSV 다운로드를 위해 원본 DataFrame에 파일명 열 추가
            report_df_with_filename = report_df.copy()
            report_df_with_filename.insert(0, "파일", filename)
            all_report_dfs.append(report_df_with_filename)
            
            # 중요도에 따라 HTML 테이블 분리
            severe_df = report_df[report_df["importance"] == "ERROR"]
            warning_df = report_df[report_df["importance"] == "WARNING"]
            
            if not severe_df.empty:
                report_data["severe_html"] = severe_df.to_html(classes="debug-table", index=False)
            if not warning_df.empty:
                report_data["warning_html"] = warning_df.to_html(classes="debug-table", index=False)

        debug_reports.append(report_data)

    final_report_df = pd.concat(all_report_dfs, ignore_index=True) if all_report_dfs else None
    
    return debug_reports, has_severe_error, final_report_df

def _run_simulation_phase(
    filepaths: Dict[str, Path],
    file_before_name: str,
    files_after_names: List[str]
) -> Dict[str, Any]:
    """
    [수정] 디버깅을 통과한 파일들에 대해 시뮬레이션을 실행합니다.
    (전처리는 이 함수 호출 전에 이미 완료되었다고 가정합니다.)

    Args:
        filepaths: 시뮬레이션 대상 파일의 경로 딕셔너리 (전처리되었거나 원본).
        file_before_name: '리모델링 전' 파일의 원본 이름.
        files_after_names: '리모델링 후' 파일들의 원본 이름 리스트.
        
    Returns:
        시뮬레이션 결과를 템플릿에 전달할 형식으로 가공한 딕셔너리.
    """
    def _execute_single_simulation(filepath: Path) -> Dict[str, Any]:
        """[수정] 내부 함수: 단일 파일 시뮬레이션 실행 (전처리 로직 제거)"""
        return run_grexcel(str(filepath), save=False)

    # '리모델링 전' 시뮬레이션 실행
    result_before = _execute_single_simulation(filepaths[file_before_name])
    
    # '리모델링 후' 시뮬레이션 실행
    results_after_list = []
    if files_after_names:
        for fname in files_after_names:
            results_after_list.append(_execute_single_simulation(filepaths[fname]))
    else:
        results_after_list.append(result_before)
        files_after_names.append(f"{file_before_name} (후 파일 미지정)")

    return {
        "filename_before": file_before_name,
        "filenames_after": files_after_names,
        "before": result_before,
        "afters": results_after_list,
    }

# ==============================================================================
# 5. 메인 실행부
# ==============================================================================
if __name__ == "__main__":
    # 실행 모드(check/run)에 따라 기본 URL('/')이 다른 기능을 수행하도록 설정
    parser = argparse.ArgumentParser(
        description="Flask web server for pyGRsim."
    )
    parser.add_argument(
        "--mode", 
        choices=["check", "run"], 
        default="run",
        help="Set the application's operating mode ('check' or 'run')."
    )
    args = parser.parse_args()

    # mode 값에 따라 루트 URL('/')에 라우트 함수를 동적으로 연결
    if args.mode == "check":
        app.add_url_rule("/", "check", check_file_validity, methods=["GET", "POST"])
    else: # 'run'이 기본값이므로 else로 처리
        app.add_url_rule("/", "run", run_simulation_comparison, methods=["GET", "POST"])

    # 디버그 모드로 Flask 앱 실행
    app.run(debug=True, host="0.0.0.0", port=5000)