import os
import shutil
from pathlib import Path

def copy_flattened(
    source_dir: str,
    target_dir: str = None,
    *,
    max_depth: int = None,
    extensions: tuple[str, ...] = None,
    overwrite: bool = False
):
    """
    지정한 source_dir 아래 모든 하위 폴더의 파일들을 하나의 폴더로 복사(flatten)하는 함수.
    
    Parameters
    ----------
    source_dir : str
        복사할 파일들이 들어 있는 루트 디렉터리 경로.
    target_dir : str, optional
        결과 파일들이 저장될 경로. 기본값은 source_dir/flattened/.
    max_depth : int, optional
        탐색할 하위 폴더의 최대 깊이. None이면 모든 깊이를 탐색.
    extensions : tuple[str, ...], optional
        복사할 파일 확장자 필터 (예: ('.jpg', '.png')). None이면 모든 확장자 포함.
    overwrite : bool, default=False
        이미 동일한 이름의 파일이 존재할 때 덮어쓸지 여부.
    """

    src = Path(source_dir).resolve()
    if target_dir is None:
        target_dir = src / "flattened"
    tgt = Path(target_dir).resolve()
    tgt.mkdir(parents=True, exist_ok=True)

    src_depth = len(src.parts)
    count = 0

    for root, _, files in os.walk(src):
        current_depth = len(Path(root).parts) - src_depth
        if max_depth is not None and current_depth > max_depth:
            continue

        for file in files:
            if extensions and not file.lower().endswith(tuple(ext.lower() for ext in extensions)):
                continue

            src_file = Path(root) / file
            dst_file = tgt / file
            
            if tgt in src_file.parents:
                continue

            # 이름 충돌 방지
            if dst_file.exists() and not overwrite:
                stem, ext = dst_file.stem, dst_file.suffix
                i = 1
                while (tgt / f"{stem}_{i}{ext}").exists():
                    i += 1
                dst_file = tgt / f"{stem}_{i}{ext}"

            shutil.copy2(src_file, dst_file)
            count += 1

    print(f"총 {count}개의 파일이 '{tgt}' 폴더로 복사되었습니다.")


if __name__ == "__main__":
    # 예시 실행
    copy_flattened(
        source_dir=r"B:\공유 드라이브\01 진행과제\(부동산원) GR정성평가\23 수신자료\251011 엑셀(현장조사포함)\251013_운영특성 데이터 반영",
        extensions="xlsx"
    )
