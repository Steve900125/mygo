from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    account_name: str = Field(max_length=32)
    password: str = Field(min_length=8, max_length=72)

class UserLogin(BaseModel):
    account_name: str
    password: str

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)
