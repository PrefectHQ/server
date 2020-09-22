import datetime
import uuid

import pendulum
from pydantic import BaseModel, validator

from prefect import models


class Event(BaseModel):

    id: str = None
    timestamp: datetime.datetime = None
    type: str = None

    @validator("timestamp", pre=True, always=True)
    def set_timestamp(cls, v):
        return v or pendulum.now("UTC")

    @validator("id", pre=True, always=True)
    def set_id(cls, v):
        return v or str(uuid.uuid4())

    @validator("type", pre=True, always=True)
    def set_type(cls, v):
        return v or cls.__name__


class FlowRunStateChange(Event):
    flow_run: models.FlowRun
    state: models.FlowRunState
    flow: models.Flow
    tenant: models.Tenant
    is_test_event: bool = False
