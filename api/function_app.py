import time

import azure.functions as func
from azurefunctions.extensions.http.fastapi import Request, StreamingResponse

app = func.FunctionApp()


def stream_response():
    for i in range(10):
        time.sleep(0.2)
        yield f"Hello, world! {i}"


@app.route(route='message', methods=['GET'])
async def message(req: Request) -> StreamingResponse:
    return StreamingResponse(
        stream_response(),
        headers={"Content-Type": "text/event-stream"},
    )
