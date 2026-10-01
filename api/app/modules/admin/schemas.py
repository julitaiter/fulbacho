from pydantic import BaseModel, ConfigDict, StrictBool, model_validator


class UserAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: StrictBool | None = None
    is_superuser: StrictBool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if self.is_active is None and self.is_superuser is None:
            raise ValueError("Enviar is_active o is_superuser como booleano")
        return self
