# ConfiguraciÃ³n de baterÃ­as

## NÃºmero de baterÃ­as

Selecciona cuÃ¡ntas unidades Marstek Venus tienes (1â€“6). La integraciÃ³n te pedirÃ¡ configurar cada una por separado.

![Control de nÃºmero de baterÃ­as](../assets/screenshots/configuration/battery-slider.png){ width="650"  style="display: block; margin: 0 auto;"}

---

## ParÃ¡metros por baterÃ­a

| ParÃ¡metro | DescripciÃ³n | Valor por defecto |
|---|---|---|
| **Nombre** | Nombre identificativo (p. ej. "Venus 1") | â€” |
| **Host** | IP del conversor Modbus TCP | â€” |
| **Puerto** | Puerto TCP Modbus | `502` |
| **VersiÃ³n** | Modelo de la baterÃ­a | â€” |
| **Potencia mÃ¡x. carga/descarga** | Potencia nominal de la instalaciÃ³n | â€” |
| **SOC mÃ¡ximo** | Detiene la carga al alcanzar este % | `100 %` |
| **SOC mÃ­nimo** | Detiene la descarga al alcanzar este % | `12 %` |
| **HistÃ©resis de carga** | Margen para evitar ciclos rÃ¡pidos cerca del lÃ­mite | â€” |
| **Umbral offgrid backup** | Carga offgrid mÃ­nima (W) para considerarse un evento de backup activo | `50 W` |

### Versiones de baterÃ­a

| VersiÃ³n | Modelos |
|---|---|
| `v1/v2` | Venus E v1, Venus E v2 |
| `v3` | Venus E v3 |
| `vA` | Venus A |
| `vD` | Venus D |

!!! warning "Potencia mÃ¡xima 2500 W"
    Usa el modo **2500 W** solo si tu instalaciÃ³n domÃ©stica puede soportar esa potencia de forma segura.

![Formulario de conexiÃ³n a la baterÃ­a](../assets/screenshots/configuration/battery-connection-form.png){ width="650"  style="display: block; margin: 0 auto;"}
![Formulario de configuraciÃ³n de baterÃ­a](../assets/screenshots/configuration/battery-config-form.png){ width="650"  style="display: block; margin: 0 auto;"}

---

## SOC y lÃ­mites de potencia en tiempo de ejecuciÃ³n

Los valores de SOC mÃ¡ximo/mÃ­nimo y potencia mÃ¡xima de carga/descarga se pueden ajustar en cualquier momento desde los sliders de la integraciÃ³n sin necesidad de reconfigurar. Los cambios se persisten y se restauran en cada reinicio de Home Assistant.

Si elevas el **SOC máximo** de una batería al `100 %`, esa batería usa protección superior por tensión: throttle de carga a 95 W desde `max_cell_voltage >= 3,48 V`, luego la carga se detiene a 3,58 V y la integración espera 60 s para registrar la medición de balance. La carga queda parada en esa tensión sin descarga forzada — la lógica normal de SOC/carga decide cuándo reanudar. Consulta [Monitor de equilibrio de celdas](../features/cell-balance-monitor.md#reduccion-por-voltaje-al-100) para las condiciones exactas de entrada y salida.

![Sliders de SOC y potencia](../assets/screenshots/configuration/battery-runtime-sliders.png){ width="650"  style="display: block; margin: 0 auto;"}

---

## Umbral offgrid backup en tiempo de ejecuciÃ³n

La entidad numÃ©rica **Umbral Offgrid Backup** (visible en la tarjeta de dispositivo de cada baterÃ­a, entre las entidades de configuraciÃ³n) permite ajustar el umbral en cualquier momento sin entrar al flujo de opciones. AumÃ©ntalo si tu baterÃ­a tiene cargas permanentes pequeÃ±as en el puerto offgrid â€” como un switch PoE, router o cÃ¡maras IP â€” que de otro modo mantendrÃ­an la baterÃ­a permanentemente excluida del control PD.

| Escenario | Umbral recomendado |
|---|---|
| Sin cargas permanentes en offgrid | `0 W` (cualquier carga activa la exclusiÃ³n) |
| Cargas pequeÃ±as (router + switch, ~20â€“40 W) | `50 W` (valor por defecto) |
| Cargas mÃ¡s pesadas (NAS, AP, cÃ¡maras, ~80â€“120 W) | `150 W` |

!!! tip "CÃ³mo funciona"
    Cuando el switch **FunciÃ³n Backup** estÃ¡ activado y la carga offgrid medida supera el umbral, la baterÃ­a queda excluida del control PD y se gestiona de forma autÃ³noma. Se aplica un perÃ­odo de enfriamiento de 5 minutos tras bajar del umbral, para evitar enviar comandos inmediatamente despuÃ©s de que termine un evento de backup.

