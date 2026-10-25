from fastapi import APIRouter, Depends, HTTPException, status

from schemas.data import DataCreate, DataItem, DataUpdate, Summary
from services.repository import Repository, get_repository
from services.summary import build_summary

router = APIRouter(prefix="/api/data", tags=["data"])


def _ensure_date_free(repo: Repository, date: str, exclude_id: str | None = None):
    existing = repo.find_data_by_date(date)
    if existing and existing["id"] != exclude_id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{date} 데이터가 이미 있습니다. 수정 기능을 사용하세요.")


@router.post("", response_model=DataItem, status_code=status.HTTP_201_CREATED, summary="새 데이터 추가")
def create_data(body: DataCreate, repo: Repository = Depends(get_repository)):
    item = body.model_dump(mode="json")
    _ensure_date_free(repo, item["date"])
    return repo.create_data(item)


@router.get("", response_model=list[DataItem], summary="데이터 목록 조회 (날짜 오름차순)")
def list_data(repo: Repository = Depends(get_repository)):
    return repo.list_data()


@router.get("/summary", response_model=Summary, summary="데이터 요약 (프롬프트 주입용)")
def get_summary(repo: Repository = Depends(get_repository)):
    return build_summary(repo.list_data())


@router.put("/{item_id}", response_model=DataItem, summary="데이터 수정 (보낸 필드만 변경)")
def update_data(item_id: str, body: DataUpdate, repo: Repository = Depends(get_repository)):
    fields = body.model_dump(mode="json", exclude_none=True)
    if "date" in fields:
        _ensure_date_free(repo, fields["date"], exclude_id=item_id)
    updated = repo.update_data(item_id, fields)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "데이터를 찾을 수 없습니다.")
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="데이터 삭제")
def delete_data(item_id: str, repo: Repository = Depends(get_repository)):
    if not repo.delete_data(item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "데이터를 찾을 수 없습니다.")
