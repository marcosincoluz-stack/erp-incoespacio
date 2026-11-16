# -*- coding: utf-8 -*-
"""Genera 4 obras de prueba: un BC3 importable y las facturas de proveedor en PDF.

Salida: una carpeta por obra, con presupuesto.bc3 y facturas/.
Los importes y los CIF son ficticios. No son documentos reales.
"""
import os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))

# Medicion: (comentario, uds, largo, ancho, alto). None no se escribe.
# La cantidad del ~D es el producto de los numeros presentes, sumado.


def m2(*rooms):
    return [(name, 1, largo, ancho, None) for name, largo, ancho in rooms]


def ml(name, metros):
    return [(name, 1, metros, None, None)]


def uds(name, n):
    return [(name, n, None, None, None)]


def m3(name, n):
    return [(name, n, None, None, None)]


OBRAS = [
    {
        "slug": "01-consulta-fisioterapia",
        "titulo": "REFORMA CONSULTA DE FISIOTERAPIA",
        "direccion": "Avda. Colon 34 bajo",
        "cliente": "Noelia Gomez Iglesias",
        "capitulos": [
            (
                "01",
                "ACTUACIONES PREVIAS",
                [
                    (
                        "01.01",
                        "Demoliciones",
                        [
                            (
                                "m2",
                                "Demolicion de tabique de ladrillo hueco",
                                18.50,
                                "Inclusive picado, carga manual y transporte a contenedor.",
                                m2(("Sala de espera", 4.20, 2.60), ("Pasillo", 6.10, 2.50)),
                            ),
                            (
                                "m2",
                                "Levantado de pavimento de terrazo",
                                14.20,
                                "Retirada de baldosa y recrecido suelto hasta encontrar el forjado.",
                                m2(("Consulta", 4.55, 3.20), ("Vestuario", 2.40, 1.80)),
                            ),
                            (
                                "ud",
                                "Desmontaje de sanitario y griferia existente",
                                28.00,
                                "Taponado provisional de desagues.",
                                uds("Aseo", 2),
                            ),
                        ],
                    ),
                    (
                        "01.02",
                        "Medios auxiliares",
                        [
                            (
                                "ud",
                                "Contenedor de escombro de 5 m3",
                                185.00,
                                "Tasas de vertedero incluidas. Retirada al finalizar la fase.",
                                uds("Retiradas", 3),
                            ),
                            (
                                "ud",
                                "Proteccion de solado y carpinteria a conservar",
                                95.00,
                                "Carton y plastico en zonas que no se demuelen.",
                                uds("Local completo", 1),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "02",
                "ALBAÑILERIA Y TABIQUERIA",
                [
                    (
                        "02.01",
                        "Tabiques",
                        [
                            (
                                "m2",
                                "Tabique de placa de yeso laminado 13 mm",
                                32.40,
                                "Doble placa, estructura de 70 mm y lana mineral.",
                                m2(("Consulta 1", 4.20, 2.70), ("Consulta 2", 3.80, 2.70)),
                            ),
                            (
                                "m2",
                                "Trasdosado autoportante de placa de yeso",
                                28.90,
                                "Sobre muro existente de fachada, con aislamiento.",
                                m2(("Fachada Colon", 8.40, 2.70)),
                            ),
                        ],
                    ),
                    (
                        "02.02",
                        "Ayudas de albanileria",
                        [
                            (
                                "m2",
                                "Recibido de premarco de puerta",
                                22.00,
                                "Recibido con mortero y retacado.",
                                uds("Puertas de paso", 4),
                            ),
                            (
                                "m2",
                                "Formacion de rozas para instalaciones",
                                16.50,
                                "Rozas en tabique nuevo, tapado posterior no incluido.",
                                ml("Rozas electricidad y fontaneria", 28.0),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "03",
                "INSTALACION ELECTRICA",
                [
                    (
                        "03.01",
                        "Cuadro y lineas",
                        [
                            (
                                "ud",
                                "Cuadro electrico de consulta con protecciones",
                                640.00,
                                "ICP, diferenciales y magnetotermicos. Esquema unifilar.",
                                uds("Cuadro general", 1),
                            ),
                            (
                                "m",
                                "Linea de alimentacion bajo tubo corrugado",
                                9.80,
                                "Cable 3x2,5 mm2 y tubo de 20 mm.",
                                ml("Distribucion de consultas", 46.0),
                            ),
                        ],
                    ),
                    (
                        "03.02",
                        "Mecanismos e iluminacion",
                        [
                            (
                                "ud",
                                "Punto de luz empotrado LED 20 W",
                                48.00,
                                "Downlight, driver y conexion a circuito.",
                                uds("Consulta 1", 4) + uds("Consulta 2", 4) + uds("Espera", 3),
                            ),
                            (
                                "ud",
                                "Base de enchufe schuko 16 A",
                                22.50,
                                "Empotrada, con tapa. Circuito de usos varios.",
                                uds("Consultas y recepcion", 14),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "04",
                "FONTANERIA Y CLIMA",
                [
                    (
                        "04.01",
                        "Aseo",
                        [
                            (
                                "ud",
                                "Inodoro de tanque bajo con asiento",
                                210.00,
                                "Inclusive llave de escuadra y latiguillo.",
                                uds("Aseo personal", 1),
                            ),
                            (
                                "ud",
                                "Lavabo mural con griferia monomando",
                                185.00,
                                "Sifon y desague a bajante existente.",
                                uds("Aseo personal", 1),
                            ),
                        ],
                    ),
                    (
                        "04.02",
                        "Climatizacion",
                        [
                            (
                                "ud",
                                "Equipo de aire acondicionado split 3,5 kW",
                                980.00,
                                "Unidad interior en consulta y exterior en patio.",
                                uds("Consulta principal", 1),
                            ),
                            (
                                "m",
                                "Linea frigorifica y desague de condensados",
                                24.00,
                                "Tuberia aislada y canaleta vista en patio.",
                                ml("Patio a consulta", 8.5),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "05",
                "PAVIMENTOS Y PINTURA",
                [
                    (
                        "05.01",
                        "Suelos",
                        [
                            (
                                "m2",
                                "Pavimento vinilico heterogeneo antideslizante",
                                36.80,
                                "Encolado sobre recrecido nivelado. Rodapie a juego.",
                                m2(("Consulta", 14.56, 1), ("Espera", 8.40, 1), ("Pasillo", 5.20, 1)),
                            ),
                            (
                                "m2",
                                "Rodapie lacado de 7 cm",
                                8.40,
                                "En el mismo tono del pavimento.",
                                ml("Perimetro de zonas reformadas", 32.0),
                            ),
                        ],
                    ),
                    (
                        "05.02",
                        "Pintura",
                        [
                            (
                                "m2",
                                "Pintura plastica lisa en paramentos",
                                7.90,
                                "Dos manos sobre emplastecido. Color a elegir por la propiedad.",
                                m2(("Paredes consulta", 28.4, 1), ("Techos", 22.0, 1)),
                            ),
                            (
                                "ud",
                                "Esmalte sobre carpinteria de madera a conservar",
                                45.00,
                                "Lijado, imprimacion y dos manos.",
                                uds("Puerta de entrada y ventana", 2),
                            ),
                        ],
                    ),
                ],
            ),
        ],
        "proveedores": [
            ("TABIQUES DEMO LEVANTE SL", "B87412033", "Poligono El Oliveral 12, Paterna"),
            ("ELECTRICIDAD DEMO COLON SL", "B30192847", "Calle Mayor 8, Valencia"),
            ("CLIMA Y FONTANERIA DEMO SL", "B55670128", "Avenida del Puerto 40, Valencia"),
        ],
    },
    {
        "slug": "02-oficina-diaphana",
        "titulo": "IMPLANTACION DE OFICINA DIAFANA",
        "direccion": "Calle Roger de Lauria 19, 3",
        "cliente": "Estudio Norte Asociados SL",
        "capitulos": [
            (
                "01",
                "DEMOLICIONES Y RESIDUOS",
                [
                    (
                        "01.01",
                        "Demolicion selectiva",
                        [
                            (
                                "m2",
                                "Demolicion de mampara de oficina existente",
                                16.20,
                                "Desmontaje de perfilería y vidrio. Acopio para gestor.",
                                m2(("Planta abierta", 18.0, 2.6), ("Sala de reuniones", 6.4, 2.6)),
                            ),
                            (
                                "m2",
                                "Levantado de moqueta en losetas",
                                6.40,
                                "Inclusive barrido y retirada a contenedor.",
                                m2(("Planta", 14.5, 12.0)),
                            ),
                        ],
                    ),
                    (
                        "01.02",
                        "Gestion de residuos",
                        [
                            (
                                "ud",
                                "Contenedor selectivo de obra",
                                160.00,
                                "Fraccion de madera, vidrio y resto.",
                                uds("Retiradas", 2),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "02",
                "PARTICIONES Y TECHOS",
                [
                    (
                        "02.01",
                        "Mamparas",
                        [
                            (
                                "m2",
                                "Mampara de vidrio laminado de despacho",
                                185.00,
                                "Perfil de aluminio anodizado, puerta abatible incluida en el metro.",
                                m2(("Despacho direccion", 4.2, 2.7), ("Sala focus", 3.2, 2.7)),
                            ),
                            (
                                "m2",
                                "Tabique de placa de yeso acustico",
                                41.50,
                                "Doble estructura y lana de roca. Para sala de reuniones.",
                                m2(("Sala reuniones", 9.6, 2.8)),
                            ),
                        ],
                    ),
                    (
                        "02.02",
                        "Techos",
                        [
                            (
                                "m2",
                                "Falso techo registrable de placa 60x60",
                                27.30,
                                "Perfilería vista y placa vinilica. Altura a definir.",
                                m2(("Planta", 16.0, 11.0)),
                            ),
                            (
                                "ud",
                                "Registro adicional de instalaciones",
                                18.00,
                                "Trampilla de 40x40 en zona de clima.",
                                uds("Pasillos tecnicos", 4),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "03",
                "ELECTRICIDAD Y DATOS",
                [
                    (
                        "03.01",
                        "Fuerza",
                        [
                            (
                                "ud",
                                "Cuadro secundario de planta",
                                890.00,
                                "Ampliacion del cuadro existente del edificio.",
                                uds("Cuarto de racks", 1),
                            ),
                            (
                                "ud",
                                "Caja de suelo para puesto de trabajo",
                                74.00,
                                "Dos enchufes y dos tomas de datos RJ45.",
                                uds("Puestos", 16),
                            ),
                        ],
                    ),
                    (
                        "03.02",
                        "Iluminacion",
                        [
                            (
                                "ud",
                                "Luminaria lineal LED suspendida",
                                126.00,
                                "1200 mm, 4000 K, regulable.",
                                uds("Eje de puestos", 12),
                            ),
                            (
                                "ud",
                                "Detector de presencia en aseo",
                                42.00,
                                "Sustitucion del interruptor existente.",
                                uds("Aseos de planta", 2),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "04",
                "CLIMATIZACION",
                [
                    (
                        "04.01",
                        "Equipos",
                        [
                            (
                                "ud",
                                "Cassette de conductos para planta abierta",
                                2450.00,
                                "Maquina existente a conservar. Esta partida es el nuevo equipo de apoyo.",
                                uds("Zona norte", 1),
                            ),
                            (
                                "ud",
                                "Split mural en sala de reuniones",
                                1120.00,
                                "3,5 kW, mando por cable.",
                                uds("Sala reuniones", 1),
                            ),
                        ],
                    ),
                    (
                        "04.02",
                        "Conductos",
                        [
                            (
                                "m2",
                                "Conducto de fibra con rejilla de impulsion",
                                48.00,
                                "Derivacion desde el cassette a la zona de direccion.",
                                m2(("Techo direccion", 6.0, 1.2)),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "05",
                "PAVIMENTO Y CARPINTERIA",
                [
                    (
                        "05.01",
                        "Suelos",
                        [
                            (
                                "m2",
                                "Suelo laminado AC5 roble",
                                29.40,
                                "Sobre foam y lamina antihumedad. Junta perimetral.",
                                m2(("Planta", 16.2, 11.4)),
                            ),
                            (
                                "m",
                                "Rodapie chapado en roble",
                                9.10,
                                "Altura 8 cm.",
                                ml("Perimetro de planta", 54.0),
                            ),
                        ],
                    ),
                    (
                        "05.02",
                        "Carpinteria",
                        [
                            (
                                "ud",
                                "Puerta de paso lacada con herraje",
                                265.00,
                                "Hoja de 82 cm, marco de pino y manilla inox.",
                                uds("Despachos y archivo", 5),
                            ),
                        ],
                    ),
                ],
            ),
        ],
        "proveedores": [
            ("MAMPARAS DEMO OFICINA SL", "B20918455", "Calle Industria 3, Valencia"),
            ("REDES Y ELECTRICIDAD DEMO SL", "B66712090", "Avenida Blasco Ibanez 90, Valencia"),
            ("SUELOS DEMO NORTE SL", "B44109823", "Poligono Fuente del Jarro, Paterna"),
        ],
    },
    {
        "slug": "03-vivienda-mayor",
        "titulo": "REFORMA INTEGRAL DE VIVIENDA",
        "direccion": "Calle Mayor 12, 2",
        "cliente": "Familia Ferrer Vidal",
        "capitulos": [
            (
                "01",
                "DEMOLICIONES",
                [
                    (
                        "01.01",
                        "Interiores",
                        [
                            (
                                "m2",
                                "Demolicion de tabique de ladrillo",
                                17.80,
                                "En cocina y pasillo. Carga incluida.",
                                m2(("Cocina", 3.4, 2.5), ("Pasillo", 4.8, 2.5)),
                            ),
                            (
                                "m2",
                                "Picado de alicatado de cocina y bano",
                                19.40,
                                "Hasta el ladrillo. Retirada de escombro.",
                                m2(("Cocina", 3.2, 2.4), ("Bano", 2.1, 2.4)),
                            ),
                        ],
                    ),
                    (
                        "01.02",
                        "Vertidos",
                        [
                            (
                                "ud",
                                "Saco y porte de escombro",
                                12.00,
                                "Sacos de 50 litros bajados a contenedor de calle.",
                                uds("Sacos", 40),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "02",
                "ALBANILERIA",
                [
                    (
                        "02.01",
                        "Cerramientos",
                        [
                            (
                                "m2",
                                "Tabique de ladrillo hueco doble",
                                34.60,
                                "Recibido con mortero y recibido de precercos.",
                                m2(("Nuevo bano", 4.6, 2.5), ("Tendedero", 2.2, 2.5)),
                            ),
                            (
                                "m2",
                                "Enfoscado maestreado de paramento",
                                14.80,
                                "Mortero de cemento, listo para alicatar.",
                                m2(("Bano", 8.4, 2.4)),
                            ),
                        ],
                    ),
                    (
                        "02.02",
                        "Techos",
                        [
                            (
                                "m2",
                                "Falso techo continuo de placa de yeso",
                                31.20,
                                "En pasillo y banos, con junta terminada.",
                                m2(("Pasillo", 6.2, 1.1), ("Bano", 2.1, 1.6)),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "03",
                "INSTALACIONES",
                [
                    (
                        "03.01",
                        "Electricidad vivienda",
                        [
                            (
                                "ud",
                                "Cuadro de vivienda con proteccion contra sobretensiones",
                                520.00,
                                "Sustitucion del cuadro de Automaticos antiguo.",
                                uds("Recibidor", 1),
                            ),
                            (
                                "ud",
                                "Punto de luz y mecanismo",
                                38.00,
                                "Interruptor y cableado nuevo en tubo.",
                                uds("Estancias reformadas", 11),
                            ),
                        ],
                    ),
                    (
                        "03.02",
                        "Fontaneria",
                        [
                            (
                                "ud",
                                "Conjunto de ducha empotrada",
                                340.00,
                                "Plato extraplano, griferia y mampara no incluida.",
                                uds("Bano principal", 1),
                            ),
                            (
                                "ud",
                                "Mueble de lavabo de 80 cm",
                                290.00,
                                "Un seno, sifon y griferia.",
                                uds("Bano principal", 1),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "04",
                "COCINA",
                [
                    (
                        "04.01",
                        "Mobiliario",
                        [
                            (
                                "m",
                                "Mueble bajo de cocina laminado",
                                280.00,
                                "Modulos de 60 y 80, zocalo y encimera postformada aparte.",
                                ml("Frente de cocina", 3.6),
                            ),
                            (
                                "m",
                                "Encimera compacta de 2 cm",
                                195.00,
                                "Canto pulido y corte de fregadero.",
                                ml("Frente de cocina", 3.6),
                            ),
                        ],
                    ),
                    (
                        "04.02",
                        "Alicatado",
                        [
                            (
                                "m2",
                                "Alicatado de gres en frente de cocina",
                                42.00,
                                "Formato 30x90, junta de 2 mm.",
                                m2(("Frente", 3.6, 0.6)),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "05",
                "ACABADOS",
                [
                    (
                        "05.01",
                        "Suelos",
                        [
                            (
                                "m2",
                                "Pavimento porcelanico imitacion madera",
                                39.50,
                                "Encolado. Nivelacion previa con pasta.",
                                m2(("Salon", 5.4, 4.2), ("Dormitorio", 3.8, 3.2), ("Pasillo", 6.0, 1.1)),
                            ),
                        ],
                    ),
                    (
                        "05.02",
                        "Pintura",
                        [
                            (
                                "m2",
                                "Pintura plastica en color suave",
                                6.80,
                                "Lijado, emplastecido y dos manos.",
                                m2(("Paredes vivienda", 22.0, 2.5)),
                            ),
                            (
                                "ud",
                                "Lijado y barnizado de puerta de paso",
                                55.00,
                                "Puertas existentes a conservar.",
                                uds("Puertas interiores", 6),
                            ),
                        ],
                    ),
                ],
            ),
        ],
        "proveedores": [
            ("ALBANILERIA DEMO MAYOR SL", "B12098451", "Calle de Quart 22, Valencia"),
            ("COCINAS DEMO HOGAR SL", "B90817263", "Avenida Tres Cruces 15, Valencia"),
            ("PINTURAS DEMO LEVANTE SL", "B33445512", "Calle San Vicente 101, Valencia"),
        ],
    },
    {
        "slug": "04-cafeteria-plaza",
        "titulo": "ACONDICIONAMIENTO DE CAFETERIA",
        "direccion": "Plaza del Ayuntamiento 4",
        "cliente": "Cafeteria La Plaza SL",
        "capitulos": [
            (
                "01",
                "ADECUACION PREVIA",
                [
                    (
                        "01.01",
                        "Vaciado",
                        [
                            (
                                "m2",
                                "Demolicion de barra de obra existente",
                                45.00,
                                "Inclusive acometidas vistas a condenar.",
                                m2(("Barra", 6.4, 1.1)),
                            ),
                            (
                                "m2",
                                "Levantado de pavimento de gres",
                                15.60,
                                "En sala y zona de barra.",
                                m2(("Sala", 9.5, 6.2)),
                            ),
                        ],
                    ),
                    (
                        "01.02",
                        "Licencias de obra",
                        [
                            (
                                "ud",
                                "Andamio de fachada para rotulo",
                                320.00,
                                "Ocupacion de via publica no incluida.",
                                uds("Fachada plaza", 1),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "02",
                "OBRA CIVIL",
                [
                    (
                        "02.01",
                        "Barra y cocina",
                        [
                            (
                                "m",
                                "Barra nueva de fabrica revestida",
                                210.00,
                                "Frente de ladrillo, listo para revestir con compacto.",
                                ml("Barra de servicio", 6.4),
                            ),
                            (
                                "m2",
                                "Solera de hormigon en cocina",
                                38.00,
                                "Espesor 8 cm, con mallazo, pendiente a sumidero.",
                                m2(("Cocina", 4.2, 3.1)),
                            ),
                        ],
                    ),
                    (
                        "02.02",
                        "Revestidos humedos",
                        [
                            (
                                "m2",
                                "Alicatado antiacido en cocina",
                                46.00,
                                "Hasta 2,10 m. Junta epoxi.",
                                m2(("Paredes cocina", 12.4, 2.1)),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "03",
                "INSTALACIONES DE HOSTELERIA",
                [
                    (
                        "03.01",
                        "Electricidad de local",
                        [
                            (
                                "ud",
                                "Cuadro de hosteleria con circuitos de fuerza",
                                1180.00,
                                "Circuitos de horno, camara, lavavajillas e iluminacion.",
                                uds("Cuadro cocina", 1),
                            ),
                            (
                                "ud",
                                "Toma de fuerza trifasica 32 A",
                                86.00,
                                "Para horno y camara.",
                                uds("Cocina", 2),
                            ),
                        ],
                    ),
                    (
                        "03.02",
                        "Fontaneria y saneamiento",
                        [
                            (
                                "ud",
                                "Punto de agua y desague de fregadero industrial",
                                145.00,
                                "Grifo ducha y sifon registrable.",
                                uds("Barra y cocina", 3),
                            ),
                            (
                                "ud",
                                "Sumidero sifonico en cocina",
                                95.00,
                                "Rejilla inox 20x20.",
                                uds("Cocina", 1),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "04",
                "CLIMA Y EXTRACCION",
                [
                    (
                        "04.01",
                        "Extraccion",
                        [
                            (
                                "ud",
                                "Campana extractora de barra con motor",
                                1640.00,
                                "Filtros y conducto hasta cubierta, maximo 6 m.",
                                uds("Barra", 1),
                            ),
                            (
                                "m",
                                "Conducto de extraccion de chapa galvanizada",
                                62.00,
                                "Tramo visto en patio, con soportes.",
                                ml("Patio interior", 6.0),
                            ),
                        ],
                    ),
                    (
                        "04.02",
                        "Climatizacion de sala",
                        [
                            (
                                "ud",
                                "Equipo cassette de sala 7 kW",
                                2280.00,
                                "Unidad exterior en cubierta.",
                                uds("Sala", 1),
                            ),
                        ],
                    ),
                ],
            ),
            (
                "05",
                "ACABADOS DE SALA",
                [
                    (
                        "05.01",
                        "Pavimentos",
                        [
                            (
                                "m2",
                                "Pavimento porcelanico antideslizante de sala",
                                41.00,
                                "Clase C3 en zona de barra, C2 en sala.",
                                m2(("Sala", 9.5, 6.2), ("Barra", 6.4, 1.2)),
                            ),
                        ],
                    ),
                    (
                        "05.02",
                        "Carpinteria y pintura",
                        [
                            (
                                "ud",
                                "Puerta cortafuegos de cocina",
                                480.00,
                                "EI2 60, barra antipanico en cara de cocina.",
                                uds("Paso a cocina", 1),
                            ),
                            (
                                "m2",
                                "Pintura plastica lavable en sala",
                                8.60,
                                "Color segun muestra de la propiedad.",
                                m2(("Paredes sala", 18.0, 3.0)),
                            ),
                        ],
                    ),
                ],
            ),
        ],
        "proveedores": [
            ("OBRA CIVIL DEMO PLAZA SL", "B77812044", "Calle Caballeros 5, Valencia"),
            ("HOSTELERIA ELECTRICA DEMO SL", "B22019876", "Poligono Vara de Quart, Valencia"),
            ("EXTRACCION Y CLIMA DEMO SL", "B61509834", "Avenida del Cid 140, Valencia"),
        ],
    },
]


def _num(value):
    if value is None:
        return ""
    text = ("%.2f" % value).rstrip("0").rstrip(".")
    return text or "0"


def _partial(row):
    total = 1.0
    present = False
    for value in row[1:]:
        if value is None:
            continue
        present = True
        total *= value
    return total if present else 0.0


def _qty(measures):
    return round(sum(_partial(row) for row in measures), 2)


def _walk(obra):
    """Capitulos, subcapitulos y partidas con codigo ya asignado."""
    chapters = []
    for ch_code, ch_name, subs in obra["capitulos"]:
        sub_out = []
        for sub_code, sub_name, items in subs:
            parts = []
            for index, (unit, summary, price, text, measures) in enumerate(items, start=1):
                code = "%s.%02d" % (sub_code, index)
                parts.append(
                    {
                        "code": code,
                        "unit": unit,
                        "summary": summary,
                        "price": price,
                        "text": text,
                        "measures": measures,
                        "qty": _qty(measures),
                        "parent": sub_code,
                    }
                )
            sub_out.append({"code": sub_code, "name": sub_name, "parts": parts})
        chapters.append({"code": ch_code, "name": ch_name, "subs": sub_out})
    return chapters


def _bc3(obra):
    lines = [
        "~V|INCOESPACIO|FIEBDC-3/2002|%s||ANSI|" % obra["titulo"],
        "~C|OBRA##||%s|0||" % obra["titulo"],
    ]
    chapters = _walk(obra)
    root_children = "".join("%s\\1\\1\\" % ch["code"] for ch in chapters)
    lines.append("~D|OBRA##|%s|" % root_children)
    for ch in chapters:
        lines.append("~C|%s#||%s|0||" % (ch["code"], ch["name"]))
        lines.append(
            "~D|%s#|%s|"
            % (ch["code"], "".join("%s\\1\\1\\" % sub["code"] for sub in ch["subs"]))
        )
        for sub in ch["subs"]:
            lines.append("~C|%s#||%s|0||" % (sub["code"], sub["name"]))
            decomp = "".join(
                "%s\\1\\%s\\" % (part["code"], _num(part["qty"])) for part in sub["parts"]
            )
            lines.append("~D|%s#|%s|" % (sub["code"], decomp))
            for part in sub["parts"]:
                lines.append(
                    "~C|%s|%s|%s|%s||"
                    % (part["code"], part["unit"], part["summary"], _num(part["price"]))
                )
                lines.append("~T|%s|%s|" % (part["code"], part["text"]))
                payload = "".join(
                    "0\\%s\\%s\\%s\\%s\\%s\\"
                    % (row[0], _num(row[1]), _num(row[2]), _num(row[3]), _num(row[4]))
                    for row in part["measures"]
                )
                lines.append("~M|%s\\%s|||%s|" % (part["parent"], part["code"], payload))
    return ("\r\n".join(lines) + "\r\n").encode("cp1252")


def _all_parts(obra):
    parts = []
    for ch in _walk(obra):
        for sub in ch["subs"]:
            parts.extend(sub["parts"])
    return parts


def _money(value):
    return "%.2f EUR" % value


def _pdf_literal(text):
    raw = text.encode("cp1252", errors="replace")
    out = bytearray(b"(")
    for byte in raw:
        if byte in b"\\()":
            out.extend(b"\\" + bytes([byte]))
        elif byte < 32 or byte > 126:
            out.extend(("\\%03o" % byte).encode("ascii"))
        else:
            out.append(byte)
    out.append(ord(")"))
    return bytes(out)


def _pdf(pages):
    """pages: lista de listas de (x, y, size, text). A4, origen abajo-izquierda."""
    objects = []

    def add(data):
        objects.append(data)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    contents = []
    for page in pages:
        stream = [b"BT"]
        for x, y, size, text in page:
            stream.append(
                b"1 0 0 1 %s %s Tm /F1 %s Tf %s Tj"
                % (_num(x).encode(), _num(y).encode(), _num(size).encode(), _pdf_literal(text))
            )
        stream.append(b"ET")
        body = b"\n".join(stream)
        contents.append(
            add(
                b"<< /Length %d >>\nstream\n" % len(body)
                + body
                + b"\nendstream"
            )
        )
    page_ids = []
    for content_id in contents:
        page_ids.append(
            add(
                b"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (font, content_id)
            )
        )
    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    pages_id = add(b"<< /Type /Pages /Count %d /Kids [%s] >>" % (len(page_ids), kids))
    # El parent se rellena ahora que conocemos el id de Pages.
    for index in page_ids:
        objects[index - 1] = objects[index - 1].replace(b"/Parent 0 0 R", b"/Parent %d 0 R" % pages_id)
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, data in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(b"%d 0 obj\n" % index)
        out.extend(data)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(b"xref\n0 %d\n" % (len(objects) + 1))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(b"%010d 00000 n \n" % offset)
    out.extend(
        b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, catalog, xref)
    )
    return bytes(out)


def _invoice_pdf(obra, proveedor, numero, fecha, lineas):
    nombre, cif, direccion = proveedor
    base = round(sum(qty * price for _, qty, price in lineas), 2)
    iva = round(base * 0.21, 2)
    total = round(base + iva, 2)
    rows = [
        (40, 800, 9, "DOCUMENTO DE PRUEBA. No es una factura real."),
        (40, 778, 14, nombre),
        (40, 762, 10, "CIF %s" % cif),
        (40, 748, 10, direccion),
        (360, 778, 14, "FACTURA"),
        (360, 760, 10, numero),
        (360, 746, 10, fecha.strftime("%d/%m/%Y")),
        (40, 710, 11, "Cliente: INCOESPACIO"),
        (40, 694, 10, "Obra: %s" % obra["titulo"]),
        (40, 680, 10, obra["direccion"]),
        (40, 650, 10, "Descripcion"),
        (360, 650, 10, "Cant."),
        (410, 650, 10, "Precio"),
        (480, 650, 10, "Importe"),
    ]
    y = 628
    for desc, qty, price in lineas:
        rows.append((40, y, 9, desc[:78]))
        rows.append((360, y, 9, _num(qty)))
        rows.append((410, y, 9, _money(price)))
        rows.append((480, y, 9, _money(round(qty * price, 2))))
        y -= 18
    y -= 10
    rows.append((360, y, 10, "Base imponible"))
    rows.append((480, y, 10, _money(base)))
    y -= 16
    rows.append((360, y, 10, "IVA 21%"))
    rows.append((480, y, 10, _money(iva)))
    y -= 16
    rows.append((360, y, 11, "Total factura"))
    rows.append((480, y, 11, _money(total)))
    y -= 28
    rows.append((40, y, 10, "IBAN de prueba: ES12 2100 0000 1100 0000 0000"))
    rows.append((40, y - 16, 9, "Forma de pago: transferencia a 30 dias."))
    return _pdf([rows])


def _invoices(obra):
    parts = _all_parts(obra)
    # Tres tandas, cada una con partidas reales del presupuesto para que el
    # emparejado por palabras tenga de donde agarrarse.
    cuts = (parts[0:4], parts[4:8], parts[8:12])
    made = []
    for index, (proveedor, seleccion) in enumerate(zip(obra["proveedores"], cuts), start=1):
        if not seleccion:
            continue
        numero = "F-2026-%s-%02d" % (obra["slug"][:2], index)
        fecha = date(2026, 3, 4 + index * 3)
        lineas = []
        for part in seleccion:
            qty = part["qty"] if part["qty"] <= 5 else round(part["qty"] * 0.4, 2)
            if qty <= 0:
                qty = 1
            # Coste por debajo del precio de venta, para simular margen.
            lineas.append((part["summary"], qty, round(part["price"] * 0.62, 2)))
        made.append((numero, fecha, proveedor, lineas))
    return made


def _check(obra, raw):
    text = raw.decode("cp1252")
    concepts = {}
    for line in text.splitlines():
        if line.startswith("~C|"):
            code = line.split("|")[1].rstrip("#")
            concepts[code] = line
    missing = []
    for line in text.splitlines():
        if not line.startswith("~D|"):
            continue
        payload = line.split("|")[2]
        bits = payload.split("\\")
        for i in range(0, len(bits) - 1, 3):
            code = bits[i]
            if code and code not in concepts:
                missing.append(code)
    if missing:
        raise SystemExit("BC3 de %s con hijos sin concepto: %s" % (obra["slug"], missing))


def main():
    for obra in OBRAS:
        folder = os.path.join(HERE, obra["slug"])
        bills = os.path.join(folder, "facturas")
        os.makedirs(bills, exist_ok=True)
        raw = _bc3(obra)
        _check(obra, raw)
        bc3_path = os.path.join(folder, "presupuesto.bc3")
        with open(bc3_path, "wb") as handle:
            handle.write(raw)
        chapters = _walk(obra)
        n_parts = sum(len(sub["parts"]) for ch in chapters for sub in ch["subs"])
        amount = 0.0
        for ch in chapters:
            for sub in ch["subs"]:
                for part in sub["parts"]:
                    amount += part["qty"] * part["price"]
        print(
            "%s  partidas=%d  presupuesto=%.2f EUR  bc3=%d bytes"
            % (obra["slug"], n_parts, amount, len(raw))
        )
        for numero, fecha, proveedor, lineas in _invoices(obra):
            path = os.path.join(bills, numero + ".pdf")
            with open(path, "wb") as handle:
                handle.write(_invoice_pdf(obra, proveedor, numero, fecha, lineas))
            print("  %s  %s" % (os.path.basename(path), proveedor[0]))


if __name__ == "__main__":
    main()
