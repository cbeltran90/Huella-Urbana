from django.http import JsonResponse


def salud(request):
    return JsonResponse({"estado": "ok"})
