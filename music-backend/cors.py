from fastapi.middleware.cors import CORSMiddleware

def setup(app):
    origins = [
        "http://localhost:4321",
        "http://127.0.0.1:4321",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"^http://(localhost|127\\.0\\.0\\.1)(:\\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600
    )