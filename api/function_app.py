import azure.functions as func

app = func.FunctionApp()

@app.route(route='message', methods=['GET'])
async def message(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        "Hello, world!"
    )
