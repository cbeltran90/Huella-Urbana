#!/usr/bin/env bash
# Descarga las librerías de frontend a static/vendor. Se corre una vez y se commitea el resultado.
set -euo pipefail
cd "$(dirname "$0")/.."

V=static/vendor
CDN=https://cdn.jsdelivr.net/npm

mkdir -p $V/htmx $V/alpine $V/leaflet/images $V/markercluster $V/leaflet-heat

get() {
  curl -fsSL "$1" -o "$2"
  echo "ok  $2 ($(wc -c < "$2") bytes)"
}

get $CDN/htmx.org@2.0.4/dist/htmx.min.js                       $V/htmx/htmx.min.js
get $CDN/alpinejs@3.14.8/dist/cdn.min.js                       $V/alpine/alpine.min.js

get $CDN/leaflet@1.9.4/dist/leaflet.js                         $V/leaflet/leaflet.js
get $CDN/leaflet@1.9.4/dist/leaflet.css                        $V/leaflet/leaflet.css
for img in layers.png layers-2x.png marker-icon.png marker-icon-2x.png marker-shadow.png; do
  get $CDN/leaflet@1.9.4/dist/images/$img                      $V/leaflet/images/$img
done

get $CDN/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js   $V/markercluster/leaflet.markercluster.js
get $CDN/leaflet.markercluster@1.5.3/dist/MarkerCluster.css          $V/markercluster/MarkerCluster.css
get $CDN/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css  $V/markercluster/MarkerCluster.Default.css

get $CDN/leaflet.heat@0.2.0/dist/leaflet-heat.js               $V/leaflet-heat/leaflet-heat.js
