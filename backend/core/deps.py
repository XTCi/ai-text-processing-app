from fastapi import Request


def get_redis(request: Request):
    return request.app.state.redis


def get_arq_pool(request: Request):
    return request.app.state.arq_pool


def get_sqlite_path(request: Request) -> str:
    return request.app.state.sqlite_path
