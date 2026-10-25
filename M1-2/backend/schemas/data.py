"""시계열 데이터 요청/응답 스키마. Pydantic이 형식·범위 검증을 맡아 라우터 코드를 단순하게 유지한다."""

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

MEMO_MAX = 200


class DataCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    date: dt.date = Field(..., description="기준 날짜 (YYYY-MM-DD)", examples=["2026-10-23"])
    # allow_inf_nan=False: NaN/Infinity 값이 통계를 깨뜨리지 않도록 차단
    value: float = Field(..., ge=0, allow_inf_nan=False, description="값 (예: 종가)", examples=[61200])
    memo: str = Field("", max_length=MEMO_MAX, description="메모", examples=["실적 발표"])


class DataUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    date: dt.date | None = None
    value: float | None = Field(None, ge=0, allow_inf_nan=False)
    memo: str | None = Field(None, max_length=MEMO_MAX)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.date is None and self.value is None and self.memo is None:
            raise ValueError("수정할 필드(date, value, memo)를 하나 이상 입력하세요.")
        return self


class DataItem(BaseModel):
    id: str
    date: dt.date
    value: float
    memo: str = ""


class Metrics(BaseModel):
    total: float
    average: float
    max: float
    max_date: dt.date
    min: float
    min_date: dt.date
    latest: float
    latest_date: dt.date
    change_pct: float = Field(..., description="첫 값 대비 마지막 값 변화율(%)")
    # 보너스: 추가 지표
    volatility_pct: float = Field(..., description="일간 변화율의 표준편차(%)")
    ma5: float = Field(..., description="최근 5개 이동평균")
    ma20: float = Field(..., description="최근 20개 이동평균")


class MonthlyStat(BaseModel):
    month: str
    average: float
    max: float
    min: float
    last: float
    count: int


class Summary(BaseModel):
    dataset: str
    unit: str
    period: str
    count: int
    metrics: Metrics | None
    trend: str
    monthly: list[MonthlyStat] = []
    recent: list[DataItem] = Field([], description="최근 데이터 포인트 (프롬프트 주입용)")
