from django.http import HttpResponse, JsonResponse


def inicio(request):
    return HttpResponse("Huella Urbana")


def salud(request):
    return JsonResponse({"estado": "ok"})
