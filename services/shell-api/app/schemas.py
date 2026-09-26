from pydantic import BaseModel, Field


class Me(BaseModel):
    sub: str
    email: str
    name: str | None = None
    groups: list[str] = Field(default_factory=list)


class AppEntry(BaseModel):
    id: str
    name: str
    description: str
    href: str
    icon: str
    tags: list[str] = Field(default_factory=list)


class SettingsOut(BaseModel):
    theme: str
    locale: str
    pinned_apps: list[str]


class SettingsPatch(BaseModel):
    theme: str | None = None
    locale: str | None = None
    pinned_apps: list[str] | None = None
