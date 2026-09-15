# Spec-Driven Development

Esta guía convierte una idea, funcionalidad, bug, auditoría o deuda técnica en GitHub
Issues pequeños, claros y verificables.

Se activa cuando el usuario menciona explícitamente **SDD**, **Spec-Driven
Development**, “crear el spec”, “especificar esta funcionalidad” o “convertir esto en
issues”.

## Comportamiento por defecto

Al invocar SDD, el agente puede:

1. Analizar la entrada y el código relacionado.
2. Buscar issues y PR existentes para evitar duplicados.
3. Dividir el trabajo en unidades ejecutables.
4. Crear automáticamente los issues necesarios mediante GitHub CLI (`gh`).
5. Devolver los números, enlaces, dependencias y orden recomendado.

No es necesaria una aprobación previa para crear issues. Si el usuario pide “solo
proponer”, “borrador” o “no publicar”, el agente debe entregar el spec sin escribir en
GitHub.

Invocar SDD no autoriza implementar, crear ramas, hacer commits, push, abrir PR ni
desplegar. Esas acciones requieren una solicitud explícita.

Todo merge cuyo destino sea `main`, incluido `develop` → `main`, requiere aprobación
explícita del usuario. Nunca debe ejecutarse automáticamente.

## Flujo

1. Entender el resultado esperado y revisar el contexto relevante.
2. Validar las afirmaciones contra el estado actual del repositorio.
3. Consultar duplicados con `gh issue list`, `gh issue view` y `gh pr list`.
4. Identificar decisiones pendientes, dependencias y riesgos.
5. Crear un issue por cada resultado que pueda implementarse y verificarse de forma
   independiente.
6. Enlazar el origen y las dependencias entre issues.
7. Asignar labels existentes cuando sean útiles; no crear taxonomías extensas sin
   necesidad.
8. Mostrar un resumen final de lo creado y señalar cualquier trabajo bloqueado.

Si falta una decisión que cambie materialmente el producto, crear un issue de
investigación o marcar el trabajo como bloqueado en vez de inventar la respuesta.

## Reglas para dividir el trabajo

- Un issue debe tener un resultado principal.
- Separar trabajo que pueda entregarse, probarse o revertirse independientemente.
- Separar decisiones de producto o arquitectura de su implementación cuando bloqueen
  el diseño.
- No dividir artificialmente por archivo.
- No crear un issue por cada párrafo de la entrada.
- Mantener los PR esperados pequeños y revisables.

## Título

Usar:

```text
[Área] Resultado concreto en infinitivo
```

Ejemplos:

```text
[Backend] Limitar el acceso a endpoints costosos
[Frontend] Mostrar el estado de error de la búsqueda
[Datos] Restringir los parámetros del RPC de búsqueda
```

Evitar títulos como “Hacer mejoras”, “Arreglar cosas” o “Implementar documento”.

## Plantilla de issue

```md
## Problema

Qué ocurre, por qué importa y cuál es la evidencia u origen.

## Alcance

- Resultado que debe producirse.
- Componentes o contratos incluidos.

## Criterios de aceptación

- [ ] Resultado principal observable.
- [ ] Caso de error, límite o compatibilidad relevante.
- [ ] Pruebas o evidencia necesarias para aceptar el cambio.

## Verificación

Comandos, pruebas o comprobaciones que demuestran el resultado.
```

Añadir únicamente cuando aporten información real:

```md
## Fuera de alcance

## Dependencias

- Bloqueado por #...
- Bloquea #...

## Riesgos y reversión

## Decisiones pendientes
```

Los criterios deben describir resultados comprobables, no intenciones como
“optimizar”, “mejorar” o “hacer seguro”. Evitar repetir la misma información en varias
secciones.

## GitHub CLI

Usar `gh` como medio predeterminado para consultar y crear issues:

```powershell
gh issue list --state all --search "texto relacionado"
gh issue view <numero> --comments
gh issue create --title "[Área] Resultado" --body-file <archivo>
```

Agregar labels, milestone o relaciones solamente si ya existen o son necesarias para
entender y ordenar el trabajo. Preferir `--body-file` para cuerpos extensos.

Después de crear cada issue, conservar su URL y comprobar que el título, cuerpo y
relaciones quedaron correctos. Si una creación falla parcialmente, consultar GitHub
antes de reintentar para no duplicarla.

## Issue listo

Un issue está listo para implementación cuando:

- el problema o necesidad fue validado;
- el alcance y los criterios son claros;
- las dependencias bloqueantes están identificadas;
- no quedan decisiones materiales sin resolver;
- la verificación es viable;
- cabe en un PR razonablemente revisable.

Usar `agent-ready` solo si esa etiqueta existe y el issue cumple estas condiciones.

## Cierre

Un issue se cierra mediante un PR con `Closes #<numero>` únicamente cuando todos sus
criterios se cumplen. Si el PR es parcial, usar `Refs #<numero>`.

La creación automática de issues no implica su implementación automática. Los merges
hacia `main` permanecen siempre bajo aprobación explícita del usuario.

## Instrucciones relacionadas

- Para implementar un issue existente o trabajar con ramas, commits, pushes, pull
  requests y merges, seguir [Git y GitHub](docs/agents/git-and-github.md).
- Antes de crear un issue, leer en [AGENTS.md](AGENTS.md) las guías correspondientes a
  cada área afectada.
