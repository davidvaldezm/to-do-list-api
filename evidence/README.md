# Evidencias verificadas de la practica 4

David Valdez Martinez | Desarrollo en la nube | 19 de noviembre de 2026

Las capturas provienen de las consolas reales de AWS y GitHub. Los JSON no contienen tfstate ni contrasenas.

| Workflow | Resultado | Evidencia |
|---|---|---|
| Provision infrastructure | success | [Run 44660190366](https://github.com/davidvaldezm/to-do-list-api/actions/runs/44660190366) |
| Destroy infrastructure | success | [Run 44660497090](https://github.com/davidvaldezm/to-do-list-api/actions/runs/44660497090) |
| CI | success | [Run 44660071377](https://github.com/davidvaldezm/to-do-list-api/actions/runs/44660071377) |
| Release | success | [Run 44648407422](https://github.com/davidvaldezm/to-do-list-api/actions/runs/44648407422) |
| Deploy release | success | [Run 44648496712](https://github.com/davidvaldezm/to-do-list-api/actions/runs/44648496712) |
| Health check | success | [Run 44660493209](https://github.com/davidvaldezm/to-do-list-api/actions/runs/44660493209) |

CI en PR: 17 pruebas aprobadas; main requiere Unit tests y Terraform validation sin bypass.

## Prueba de ejecucion

- `runtime-baseline.json`: cinco POST con HTTP 201 y posterior lectura de las mismas tareas.
- `runtime-deployed.json`: version 1.0.0 y persistencia despues del deploy automatico.
- `runtime-outage.json`: GET /health y GET /tasks responden 503 con RDS detenido.
- `metrics-outage.json`: RdsErrors mayor a cero y alarma ALARM por datos reales.
- `alarm-history.json`: transiciones OK -> ALARM -> OK y acciones SNS exitosas.
- `runtime-recovered.json`: version 1.0.0, HTTP 200 y las cinco tareas conservadas tras iniciar RDS.
- `sns-confirmed.json`: suscripcion de correo confirmada; el endpoint privado se omite.
- `main-protection.json` y `06-main-protection.jpg`: checks obligatorios del repositorio.
- `ci/test-results.xml`: reporte JUnit generado por GitHub Actions.

## Capturas obligatorias

- `01-dashboard.jpg`: dashboard con las tres metricas, incluido el pico de errores y recuperacion.
- `02-rds-alarm.jpg`: alarma real en estado ALARM.
- `03-remote-state.jpg`: objeto de estado en S3 durante el aprovisionamiento completo.

## Estado final

Destroy se ejecuto con exito sobre los recursos de esta practica. El bucket S3 cifrado, privado y versionado conserva ambos estados.
El cron de salud queda desactivado durante el apagado intencional y Provision lo reactiva automaticamente.
Los recursos anteriores de otras practicas no se eliminaron. Para recrear, renovar los tres secrets temporales AWS y ejecutar Provision.
