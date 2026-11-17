"""Mascotas de los datos de prueba: fichas, fotos, publicaciones y recorridos.

Cada historia pasa por los servicios reales, como lo haría una persona desde la web. Las
mascotas se cargan una sola vez: si ya están, no se toca nada (para empezar de cero, --vaciar).
"""

from datetime import timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from apps.adopcion import eleccion, entrega
from apps.adopcion.postulaciones import postular_adopcion
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import agregar_fotografias, crear_ficha
from apps.publicaciones import resolucion, servicios, vinculacion
from apps.publicaciones.models import Publicacion
from apps.publicaciones.moderacion import eliminar_publicacion
from apps.transito import eleccion as eleccion_hogar
from apps.transito import ingreso, solicitud
from apps.transito.postulaciones import postular_transito

from .lugares import punto

FOTOS = Path(__file__).parent / "fotos"
PRIMERA = "Nina"  # si su ficha existe, las mascotas ya están cargadas


def foto(nombre):
    """Una foto de la carpeta "fotos" como si la subiera una persona."""
    ruta = FOTOS / f"{nombre}.jpg"
    return SimpleUploadedFile(ruta.name, ruta.read_bytes(), content_type="image/jpeg")


def hace(publicacion, dias, *, urgente=False):
    """Fecha la publicación "dias" atrás, para que el listado no salga todo de hoy."""
    Publicacion.objects.filter(pk=publicacion.pk).update(
        fecha=timezone.now() - timedelta(days=dias), etiqueta_urgente=urgente
    )


def animal(nombre, especie, tamano, color, **extra):
    return {"nombre": nombre, "especie": especie, "tamano": tamano, "color": color, **extra}


@transaction.atomic
def cargar_mascotas(u):
    """Carga todas las historias. "u" es {clave: usuario} de cargar_personas."""
    if FichaAnimal.objects.filter(nombre=PRIMERA).exists():
        return False
    _fichas_privadas(u)
    _perdidos(u)
    _recorrido_de_transito_y_adopcion(u)
    _altas_en_adopcion(u)
    return True


def _fichas_privadas(u):
    """Alta preventiva: fichas de dueños que no perdieron a su mascota."""
    pipo = crear_ficha(
        u["joaquin"],
        animal("Pipo", "gato", "mediano", "atigrado", raza="mestizo", castrado=True, vacunado=True),
    )
    agregar_fotografias(pipo, u["joaquin"], [foto("gato-atigrado-gris")])
    thor = crear_ficha(
        u["nicolas"],
        animal("Thor", "perro", "grande", "gris", raza="pitbull", chip="032-100-200-300"),
    )
    agregar_fotografias(thor, u["nicolas"], [foto("perro-gris-pecho-blanco")])
    kiara = crear_ficha(u["carla"], animal("Kiara", "gato", "pequeno", "marrón", castrado=True))
    agregar_fotografias(kiara, u["carla"], [foto("gato-siames-oscuro")])


# (persona, animal, foto, descripción, hace cuántos días)
OTROS_EXTRAVIOS = [
    (
        "romina",
        animal("Pancho", "perro", "pequeno", "crema"),
        "perro-crema-pequeno",
        "Se escapó cuando abrimos el portón.",
        3,
    ),
    (
        "tomas",
        animal("Milo", "gato", "mediano", "gris y blanco", castrado=True),
        "gato-gris-y-blanco",
        "Nunca sale de casa; debe estar escondido cerca.",
        5,
    ),
    (
        "martin",
        animal("Felipe", "gato", "grande", "atigrado"),
        "gato-atigrado-viejo",
        "Es viejito y no ve bien.",
        12,
    ),
    (
        "joaquin",
        animal("Sombra", "gato", "mediano", "negro"),
        "gato-negro-peludo",
        "Pelo largo, muy miedoso.",
        2,
    ),
    (
        "emanuel",
        animal("Canela", "perro", "mediano", "marrón claro"),
        "perro-marron-claro",
        "Lleva collar azul con su nombre.",
        1,
    ),
]

# (persona, animal, foto, lugar, descripción, hace cuántos días, lo tiene consigo)
OTROS_HALLAZGOS = [
    (
        "ana",
        animal("", "perro", "pequeno", "blanco"),
        "perro-blanco-pequeno",
        "alto_ecologico_este",
        "Andaba suelto por la calle. Lo tengo en casa.",
        2,
        True,
    ),
    (
        "martin",
        animal("", "gato", "mediano", "atigrado"),
        "gato-atigrado-patio-1",
        "mision_baja",
        "Duerme en el patio del edificio hace una semana.",
        6,
        False,
    ),
    (
        "nicolas",
        animal("", "gato", "mediano", "atigrado"),
        "gato-atigrado-marron",
        "los_pinos",
        "Pide comida en la puerta todas las noches.",
        4,
        False,
    ),
    (
        "camila",
        animal("", "perro", "grande", "tostado"),
        "perro-tostado-grande",
        "calafate",
        "Grandote y bonachón, sigue a la gente por la calle.",
        3,
        False,
    ),
    (
        "agustina",
        animal("", "perro", "pequeno", "negro y fuego", edad_estimada="cachorro"),
        "cachorro-negro-y-fuego",
        "canadon_del_parque",
        "Cachorro solo en la plaza.",
        1,
        False,
    ),
]


def _perdidos(u):
    """Extravíos y hallazgos: vigentes, con coincidencias en cada estado y casos cerrados."""
    # Nina: extravío urgente y un hallazgo de la misma gata; Camila la vinculó y Sofía tiene
    # que decidir (coincidencia pendiente, para mostrarla en vivo).
    nina = servicios.publicar_extravio(
        u["sofia"],
        animal=animal(
            "Nina", "gato", "mediano", "atigrado", raza="mestizo", requiere_medicacion=True
        ),
        archivo=foto("gata-atigrada-collar-rojo-1"),
        descripcion="Collar rojo con cascabel. Toma medicación para la tiroides todos los días.",
    )
    hace(nina, 2, urgente=True)
    gata = servicios.publicar_hallazgo(
        u["camila"],
        animal=animal("", "gato", "mediano", "atigrado"),
        archivo=foto("gata-atigrada-collar-rojo-2"),
        punto=punto("peron_alto"),
        descripcion="Estaba en la escalera del edificio, con collar rojo. Es muy mansa.",
        estado_aparente="Bien, un poco asustada",
        tiene_consigo=True,
    )
    hace(gata, 1)
    vinculacion.proponer_coincidencias(gata)
    vinculacion.vincular(gata, nina.ficha, u["camila"])

    # Rocco: Florencia lo encontró, Nicolás confirmó que es él y cerró el caso (final feliz).
    rocco = servicios.publicar_extravio(
        u["nicolas"],
        animal=animal("Rocco", "perro", "mediano", "blanco", raza="mestizo"),
        archivo=foto("perro-blanco-cabeza-negra-1"),
        descripcion="Blanco con la cabeza negra. Se asustó con la pirotecnia.",
    )
    hace(rocco, 6)
    perro = servicios.publicar_hallazgo(
        u["florencia"],
        animal=animal("", "perro", "mediano", "blanco"),
        archivo=foto("perro-blanco-cabeza-negra-2"),
        punto=punto("la_cantera"),
        descripcion="Apareció en el patio. Tiene collar pero sin chapita.",
        tiene_consigo=True,
    )
    hace(perro, 5)
    vinculacion.proponer_coincidencias(perro)
    coincidencia = vinculacion.vincular(perro, rocco.ficha, u["florencia"])
    vinculacion.responder(coincidencia, u["nicolas"], confirmar=True)
    resolucion.resolver_caso(rocco.ficha, u["nicolas"])

    # Toby: Matías encontró un perro parecido, pero Sebastián lo descartó; Toby sigue perdido.
    toby = servicios.publicar_extravio(
        u["sebastian"],
        animal=animal("Toby", "perro", "mediano", "blanco y negro", raza="mestizo"),
        archivo=foto("perro-blanco-y-negro-1"),
        descripcion="Es mayor y camina despacio. Responde a su nombre.",
    )
    agregar_fotografias(toby.ficha, u["sebastian"], [foto("perro-blanco-y-negro-2")])
    hace(toby, 10)
    parecido = servicios.publicar_hallazgo(
        u["matias"],
        animal=animal("", "perro", "mediano", "crema"),
        archivo=foto("perro-crema-mestizo"),
        punto=punto("el_libertador"),
        descripcion="Lo tengo en casa. Es tranquilo y se lleva bien con los chicos.",
        tiene_consigo=True,
    )
    hace(parecido, 3)
    vinculacion.proponer_coincidencias(parecido)
    descartada = vinculacion.vincular(parecido, toby.ficha, u["matias"])
    vinculacion.responder(descartada, u["sebastian"], confirmar=False)

    # Luna: extravío reciente, sin novedades.
    luna = servicios.publicar_extravio(
        u["agustina"],
        animal=animal("Luna", "gato", "mediano", "negro", castrado=True),
        archivo=foto("gata-negra"),
        descripcion="Salió por el balcón. Tiene un ojo de cada color.",
    )
    hace(luna, 1)

    # Kira: se perdió y volvió sola; Julieta cerró el caso.
    kira = servicios.publicar_extravio(
        u["julieta"],
        animal=animal("Kira", "perro", "grande", "amarillo", raza="mestizo"),
        archivo=foto("perro-amarillo-pretal"),
        descripcion="Tiene pretal marrón.",
    )
    hace(kira, 15)
    resolucion.resolver_caso(kira.ficha, u["julieta"])

    # Hallazgos sin dueño: uno que Paula solo vio en la calle y otro que Federico tiene.
    visto = servicios.publicar_hallazgo(
        u["paula"],
        animal=animal("", "gato", "mediano", "negro"),
        archivo=foto("gato-negro-afuera"),
        punto=punto("rio_pipo"),
        descripcion="Anda por la cuadra hace días. No se deja agarrar.",
    )
    hace(visto, 4)
    colorado = servicios.publicar_hallazgo(
        u["federico"],
        animal=animal("", "perro", "pequeno", "colorado"),
        archivo=foto("perro-colorado-nieve"),
        punto=punto("bahia_golondrina"),
        descripcion="Estaba en la nieve, con frío. Lo tenemos en casa hasta encontrar al dueño.",
        estado_aparente="Flaco pero bien",
        tiene_consigo=True,
    )
    hace(colorado, 2)

    # Más avisos, para que el mapa y los listados muestren toda la ciudad.
    for clave, datos, nombre_foto, descripcion, dias in OTROS_EXTRAVIOS:
        extravio = servicios.publicar_extravio(
            u[clave], animal=datos, archivo=foto(nombre_foto), descripcion=descripcion
        )
        hace(extravio, dias)
    for clave, datos, nombre_foto, lugar, descripcion, dias, consigo in OTROS_HALLAZGOS:
        hallazgo = servicios.publicar_hallazgo(
            u[clave],
            animal=datos,
            archivo=foto(nombre_foto),
            punto=punto(lugar),
            descripcion=descripcion,
            tiene_consigo=consigo,
        )
        hace(hallazgo, dias)

    # Un aviso falso de Marcos con la foto de Thor, el perro de Nicolás: la foto quedó marcada
    # como duplicada y la moderadora eliminó el aviso.
    falso = servicios.publicar_extravio(
        u["marcos"],
        animal=animal("", "perro", "grande", "gris"),
        archivo=foto("perro-gris-pecho-blanco"),
        descripcion="Vendo cachorros iguales a este. Escribime.",
    )
    hace(falso, 8)
    eliminar_publicacion(falso, u["gabriela"])


def _rescate(u, datos, nombre_foto, lugar, descripcion):
    """Emanuel encuentra un animal y lo tiene en su casa (ficha sin responsable a su cargo)."""
    hallazgo = servicios.publicar_hallazgo(
        u["emanuel"],
        animal=datos,
        archivo=foto(nombre_foto),
        punto=punto(lugar),
        descripcion=descripcion,
        tiene_consigo=True,
    )
    return hallazgo.ficha


def _a_un_hogar(u, ficha, hogar):
    """Emanuel pide tránsito, el hogar se postula, lo elige y se lo entrega."""
    solicitud.solicitar_transito(ficha, u["emanuel"])
    postulacion = postular_transito(u[hogar], ficha, "Por WhatsApp")
    eleccion_hogar.elegir_hogar(ficha, u["emanuel"], postulacion)
    ingreso.registrar_ingreso(ficha, u["emanuel"], vacunado=True, desparasitado=True)
    ficha.refresh_from_db()
    return ficha


def _recorrido_de_transito_y_adopcion(u):
    """Lo que encontró Emanuel, cada uno frenado en un paso distinto del recorrido."""
    # Lola: todavía en su casa; Emanuel tiene que pedir un hogar de tránsito.
    _rescate(
        u,
        animal("Lola", "perro", "mediano", "tostado", edad_estimada="2 años"),
        "perro-tostado-peludo",
        "andino",
        "La encontré en el camino al glaciar. Es muy cariñosa.",
    )
    # Toto: pidió tránsito y se postularon Lucía y Romina; Emanuel tiene que elegir.
    toto = _rescate(
        u,
        animal("Toto", "perro", "grande", "negro y fuego", problemas_conducta=True),
        "perro-negro-y-fuego",
        "kaiken",
        "Ladra mucho a otros perros, con personas es un amor.",
    )
    solicitud.solicitar_transito(toto, u["emanuel"])
    for hogar in ("lucia", "romina"):
        postular_transito(u[hogar], toto, "Por WhatsApp")
    # Nube: Martín fue elegido; falta registrar que llegó a su casa.
    nube = _rescate(
        u,
        animal("Nube", "gato", "pequeno", "blanco", edad_estimada="6 meses"),
        "gato-blanco",
        "itulara",
        "Gatita muy chiquita, estaba sola en un contenedor.",
    )
    solicitud.solicitar_transito(nube, u["emanuel"])
    postulacion = postular_transito(u["martin"], nube, "Por mensaje")
    eleccion_hogar.elegir_hogar(nube, u["emanuel"], postulacion)
    # Rocky: en lo de Lucía, con Ana y Federico postulados para adoptarlo.
    rocky = _a_un_hogar(
        u,
        _rescate(
            u,
            animal("Rocky", "perro", "mediano", "marrón", compatible_ninos=True),
            "perro-marron-collar",
            "las_lengas",
            "Muy juguetón, ideal para una familia.",
        ),
        "lucia",
    )
    postular_adopcion(u["ana"], rocky, "ana.benitez@example.com")
    postular_adopcion(u["federico"], rocky, "Por WhatsApp")
    # Mora: en lo de Lucía, con Ana elegida; falta concretar la adopción.
    mora = _a_un_hogar(
        u,
        _rescate(
            u,
            animal("Mora", "perro", "mediano", "crema", compatible_animales=True),
            "perra-crema-mediana",
            "penaloza",
            "Tranquila, se lleva bien con otros perros.",
        ),
        "lucia",
    )
    elegida = postular_adopcion(u["ana"], mora, "Por WhatsApp")
    eleccion.elegir_adoptante(elegida, u["lucia"])
    # Coco: perro grande con medicación en lo de Diego, que quedó con el cupo lleno.
    _a_un_hogar(
        u,
        _rescate(
            u,
            animal("Coco", "perro", "grande", "dorado", requiere_medicacion=True),
            "perro-dorado-viejo",
            "tolkar",
            "Es mayor y toma un remedio para las articulaciones.",
        ),
        "diego",
    )
    # Un perro que nadie tiene a cargo: la moderadora pidió tránsito con el contacto de la
    # veterinaria que lo cuida (extensión 1A de CU-24).
    callejero = servicios.publicar_hallazgo(
        u["julieta"],
        animal=animal("", "perro", "grande", "gris"),
        archivo=foto("perro-gris-peludo"),
        punto=punto("pedro_fique"),
        descripcion="Lo llevamos a la veterinaria del barrio, que lo cuida unos días.",
    )
    solicitud.solicitar_transito(
        callejero.ficha,
        u["gabriela"],
        contacto="Veterinaria del barrio, 2901 555-0142",
        punto=punto("pedro_fique"),
    )


def _altas_en_adopcion(u):
    """Altas directas en adopción, una con postulaciones y una adopción ya concretada."""
    michi = servicios.alta_en_adopcion(
        u["florencia"],
        animal=animal("Michi", "gato", "pequeno", "atigrado", edad_estimada="4 meses"),
        archivos=[foto("gata-atigrada-joven")],
        descripcion="Nació en casa. Come solo y usa la piedrita.",
        telefono_visible="2901 555-0177",
    )
    hace(michi, 3)
    postular_adopcion(u["carla"], michi.ficha, "carla.medina@example.com")
    postular_adopcion(u["paula"], michi.ficha, "Por WhatsApp")

    naranja = servicios.alta_en_adopcion(
        u["agustina"],
        animal=animal("Tango", "gato", "mediano", "naranja y blanco", castrado=True),
        archivos=[foto("gato-naranja-y-blanco")],
        descripcion="Me mudo y no puedo llevarlo. Es muy compañero.",
    )
    hace(naranja, 7)

    # Simba ya encontró familia: Paula lo adoptó.
    simba = servicios.alta_en_adopcion(
        u["sebastian"],
        animal=animal("Simba", "gato", "grande", "tricolor", castrado=True, vacunado=True),
        archivos=[foto("gato-tricolor-peludo")],
        descripcion="Gato adulto, tranquilo y muy limpio.",
    )
    hace(simba, 20)
    elegida = postular_adopcion(u["paula"], simba.ficha, "Por WhatsApp")
    eleccion.elegir_adoptante(elegida, u["sebastian"])
    entrega.concretar_adopcion(simba.ficha, u["sebastian"])
