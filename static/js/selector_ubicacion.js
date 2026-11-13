/* Selector de ubicación compartido: se marca un punto tocando el mapa o con el GPS.
 *
 * Lo usan las pantallas que piden una ubicación (domicilio, solicitar tránsito y las
 * publicaciones). Necesita en la página: el fragmento "_selector_ubicacion.html" (botón, mapa
 * y campos ocultos) y "_selector_ubicacion_js.html" (que llama a iniciar).
 */
(function () {
  function leer(id) {
    const elemento = document.getElementById(id);
    return elemento ? JSON.parse(elemento.textContent) : null;
  }

  function iniciar(mapaId) {
    const config = leer("mapa-config");
    const centro = leer("mapa-centro");
    const campoLat = document.getElementById("id_latitud");
    const campoLng = document.getElementById("id_longitud");
    const mapa = L.map(mapaId).setView([-54.8019, -68.3030], 13);
    L.tileLayer(config.tiles_url, { maxZoom: 19, attribution: config.atribucion }).addTo(mapa);
    window.mapaUbicacion = mapa;
    let marcador = null;

    function ponerMarcador(lat, lng) {
      if (marcador) {
        marcador.setLatLng([lat, lng]);
      } else {
        marcador = L.marker([lat, lng]).addTo(mapa);
      }
    }

    function marcar(lat, lng) {
      campoLat.value = lat;
      campoLng.value = lng;
      ponerMarcador(lat, lng);
    }

    if (campoLat.value && campoLng.value) {
      marcar(parseFloat(campoLat.value), parseFloat(campoLng.value));
      mapa.setView([campoLat.value, campoLng.value], 15);
    } else if (centro) {
      ponerMarcador(centro.lat, centro.lng);
      mapa.setView([centro.lat, centro.lng], 15);
    }

    mapa.on("click", function (e) {
      marcar(e.latlng.lat, e.latlng.lng);
    });

    document.getElementById("boton-gps").addEventListener("click", function () {
      if (!navigator.geolocation) {
        return;
      }
      navigator.geolocation.getCurrentPosition(function (pos) {
        marcar(pos.coords.latitude, pos.coords.longitude);
        mapa.setView([pos.coords.latitude, pos.coords.longitude], 16);
      });
    });

    return mapa;
  }

  window.SelectorUbicacion = { iniciar: iniciar };
})();
