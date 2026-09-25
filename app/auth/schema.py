from pydantic import BaseModel


class UserCredentials(BaseModel):
    email: str
    password: str


class RegisterCredentials(BaseModel):
    email: str
    password: str
    username: str
