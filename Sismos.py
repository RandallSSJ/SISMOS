import sqlite3
import requests
from datetime import datetime

conexion = sqlite3.connect("sismos_nicaragua.db")

cursor = conexion.cursor()

cursor.execute("PRAGMA foreign_keys = ON")

cursor.executescript("""

DROP VIEW IF EXISTS vista_sismos_fuertes;
DROP VIEW IF EXISTS vista_sismos_completa;

DROP TRIGGER IF EXISTS trg_validar_magnitud;
DROP TRIGGER IF EXISTS trg_validar_profundidad;

DROP TABLE IF EXISTS sismos;
DROP TABLE IF EXISTS lugares;
DROP TABLE IF EXISTS categorias_magnitud;

CREATE TABLE categorias_magnitud(

    id_categoria INTEGER PRIMARY KEY,

    nombre_categoria TEXT NOT NULL UNIQUE,

    magnitud_min REAL NOT NULL,

    magnitud_max REAL NOT NULL,

    CHECK(magnitud_min >= 0),

    CHECK(magnitud_max > magnitud_min)

);

CREATE TABLE lugares(

    id_lugar INTEGER PRIMARY KEY AUTOINCREMENT,

    nombre TEXT NOT NULL,

    latitud REAL NOT NULL,

    longitud REAL NOT NULL,

    UNIQUE(nombre, latitud, longitud),

    CHECK(latitud BETWEEN -90 AND 90),

    CHECK(longitud BETWEEN -180 AND 180)

);

CREATE TABLE sismos(

    id_sismo TEXT PRIMARY KEY,

    fecha TEXT NOT NULL,

    magnitud REAL NOT NULL,

    profundidad REAL NOT NULL,

    id_lugar INTEGER NOT NULL,

    id_categoria INTEGER NOT NULL,

    FOREIGN KEY(id_lugar)
        REFERENCES lugares(id_lugar),

    FOREIGN KEY(id_categoria)
        REFERENCES categorias_magnitud(id_categoria),

    CHECK(magnitud >= 0),

    CHECK(profundidad >= 0)

);

CREATE INDEX idx_sismos_fecha
ON sismos(fecha);

CREATE INDEX idx_sismos_magnitud
ON sismos(magnitud);

CREATE INDEX idx_sismos_profundidad
ON sismos(profundidad);

CREATE INDEX idx_lugares_nombre
ON lugares(nombre);

CREATE VIEW vista_sismos_fuertes AS

SELECT

    s.id_sismo,
    s.fecha,
    s.magnitud,
    s.profundidad,
    l.nombre

FROM sismos s

INNER JOIN lugares l
ON s.id_lugar = l.id_lugar

WHERE s.magnitud >= 6;

CREATE VIEW vista_sismos_completa AS

SELECT

    s.id_sismo,
    s.fecha,
    s.magnitud,
    s.profundidad,

    l.nombre,
    l.latitud,
    l.longitud,

    c.nombre_categoria

FROM sismos s

INNER JOIN lugares l
ON s.id_lugar = l.id_lugar

INNER JOIN categorias_magnitud c
ON s.id_categoria = c.id_categoria;

CREATE TRIGGER trg_validar_magnitud

BEFORE INSERT ON sismos

FOR EACH ROW

WHEN NEW.magnitud < 0

BEGIN

    SELECT RAISE(
        ABORT,
        'Magnitud invalida'
    );

END;

CREATE TRIGGER trg_validar_profundidad

BEFORE INSERT ON sismos

FOR EACH ROW

WHEN NEW.profundidad < 0

BEGIN

    SELECT RAISE(
        ABORT,
        'Profundidad invalida'
    );

END;

""")

cursor.execute("""
INSERT INTO categorias_magnitud
VALUES (1,'Leve',0,3.9)
""")

cursor.execute("""
INSERT INTO categorias_magnitud
VALUES (2,'Moderado',4,5.9)
""")

cursor.execute("""
INSERT INTO categorias_magnitud
VALUES (3,'Fuerte',6,10)
""")

url = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query"
    "?format=geojson"
    "&starttime=2000-01-01"
    "&endtime=2026-12-31"
    "&minlatitude=10"
    "&maxlatitude=16"
    "&minlongitude=-88"
    "&maxlongitude=-82"
)

print("Descargando datos de la API...")

respuesta = requests.get(url)

datos = respuesta.json()

contador = 0

for item in datos["features"]:

    try:

        id_sismo = item["id"]

        magnitud = item["properties"]["mag"]

        if magnitud is None:
            continue

        fecha = datetime.fromtimestamp(
            item["properties"]["time"] / 1000
        ).strftime("%Y-%m-%d %H:%M:%S")

        lugar = item["properties"]["place"]

        longitud = item["geometry"]["coordinates"][0]
        latitud = item["geometry"]["coordinates"][1]
        profundidad = item["geometry"]["coordinates"][2]

        if magnitud < 4:
            categoria = 1
        elif magnitud < 6:
            categoria = 2
        else:
            categoria = 3

        cursor.execute("""
        INSERT OR IGNORE INTO lugares
        (
            nombre,
            latitud,
            longitud
        )
        VALUES (?, ?, ?)
        """,
        (
            lugar,
            latitud,
            longitud
        ))

        cursor.execute("""
        SELECT id_lugar
        FROM lugares
        WHERE nombre = ?
        AND latitud = ?
        AND longitud = ?
        """,
        (
            lugar,
            latitud,
            longitud
        ))

        id_lugar = cursor.fetchone()[0]

        cursor.execute("""
        INSERT OR IGNORE INTO sismos
        (
            id_sismo,
            fecha,
            magnitud,
            profundidad,
            id_lugar,
            id_categoria
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            id_sismo,
            fecha,
            magnitud,
            profundidad,
            id_lugar,
            categoria
        ))

        contador += 1

    except Exception as e:

        print("Error:", e)

conexion.commit()

cursor.execute("""
SELECT COUNT(*)
FROM sismos
""")

total_sismos = cursor.fetchone()[0]

cursor.execute("""
SELECT COUNT(*)
FROM lugares
""")

total_lugares = cursor.fetchone()[0]

print()
print("Proceso finalizado")
print(f"Sismos guardados: {total_sismos}")
print(f"Lugares guardados: {total_lugares}")
print(f"Registros procesados: {contador}")

conexion.close()