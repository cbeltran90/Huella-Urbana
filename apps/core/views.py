from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


def inicio(request):
    return render(request, "inicio.html")


def salud(request):
    return JsonResponse({"estado": "ok"})


def prueba(request):
    return render(request, "prueba.html")


def prueba_saludo(request):
    return HttpResponse("¡Hola desde el servidor! Este HTML llegó por HTMX.")
