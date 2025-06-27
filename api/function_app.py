import azure.functions as func
from azurefunctions.extensions.http.fastapi import Request, StreamingResponse

app = func.FunctionApp()

@app.route(route='message', methods=['GET'])
async def message(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        "Hello, world!"
    )
