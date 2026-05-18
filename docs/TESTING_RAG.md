# Guía para Ejecutar Pruebas del Motor RAG

## Requisitos Previos

Antes de ejecutar las pruebas del motor RAG, asegúrate de tener:

1. **Neo4j Desktop corriendo**
2. **Base de datos iniciada** con los datos ingestados
3. **Variables de entorno configuradas** (`.env` o en la sesión de PowerShell)

---

## Paso 1: Iniciar Neo4j

### Opción A: Neo4j Desktop
1. Abre **Neo4j Desktop**
2. Selecciona tu proyecto (probablemente "TIC_ABSA_KG")
3. Haz clic en **"Start"** en la base de datos
4. Espera a que el estado cambie a **"Running"**
5. Verifica la URI de conexión (debería ser `bolt://localhost:7687` o `neo4j://localhost:7687`)

### Opción B: Neo4j Community (Línea de Comandos)
```powershell
# Si instalaste Neo4j manualmente
cd "C:\path\to\neo4j"
.\bin\neo4j.bat console
```

---

## Paso 2: Verificar Conectividad

Abre el navegador de Neo4j:
- URL: http://localhost:7474
- Usuario: `neo4j`
- Contraseña: (la que configuraste)

Ejecuta esta consulta para verificar que hay datos:
```cypher
MATCH (c:Comment) RETURN count(c) as total_comments
```

Deberías ver ~6,861 comentarios.

---

## Paso 3: Ejecutar Pruebas Exhaustivas

### Opción 1: Con API Key en la sesión
```powershell
cd C:\Users\JEanpa\Documents\GitHub\TIC_ABSA_KG

# Configurar API Key
$env:OPENAI_API_KEY='tu-api-key-aqui'

# Ejecutar pruebas
python src/rag/test_rag_comprehensive.py
```

### Opción 2: Con archivo .env
Asegúrate de que tu archivo `.env` contenga:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=tu_password
OPENAI_API_KEY=tu_api_key
```

Luego ejecuta:
```powershell
python src/rag/test_rag_comprehensive.py
```

---

## Paso 4: Interpretar Resultados

El script ejecutará 8 pruebas:

1. **✅ Conectividad**: Verifica conexión a Neo4j
2. **✅ Existencia de Datos**: Cuenta nodos y verifica índice vectorial
3. **✅ Consulta General**: Pregunta sin filtro de curso
4. **✅ Consulta Filtrada**: Pregunta con filtro de curso específico
5. **✅ Reporte Ejecutivo**: Genera reporte de un curso
6. **✅ Curso Inexistente**: Manejo de errores
7. **✅ Caching**: Verifica mejora de performance en segunda consulta
8. **✅ Consulta sin Resultados**: Manejo de preguntas irrelevantes

### Resultado Esperado
```
📊 Resultado Final: 8/8 pruebas exitosas (100.0%)
🎉 ¡Todas las pruebas pasaron! El sistema RAG está funcionando correctamente.
```

---

## Pruebas Individuales (Alternativas)

Si prefieres probar componentes específicos:

### Prueba Rápida de Consulta
```powershell
python src/rag/rag_engine.py "¿Qué opinan sobre la evaluación?"
```

### Prueba de Reporte de Curso
```python
from src.rag.rag_engine import GraphRAGEngine

engine = GraphRAGEngine()
report = engine.get_course_report("course-v1:UTPL+HG+2016")
print(report)
engine.close()
```

### Prueba de Fase 3 (Performance)
```powershell
python src/rag/test_phase3.py
```

---

## Troubleshooting

### Error: "Couldn't connect to localhost:7687"
**Solución:** Neo4j no está corriendo. Inicia Neo4j Desktop.

### Error: "OPENAI_API_KEY no encontrada"
**Solución:** Configura la variable de entorno:
```powershell
$env:OPENAI_API_KEY='sk-proj-...'
```

### Error: "No se encontró información relevante"
**Solución:** Verifica que los datos estén ingestados:
```cypher
MATCH (c:Comment) WHERE c.embedding IS NOT NULL RETURN count(c)
```

### Error: "Index 'comment_embedding' not found"
**Solución:** Ejecuta el script de ingesta:
```powershell
python src/rag/neo4j_ingest.py
```

---

## Próximos Pasos

Una vez que todas las pruebas pasen:

1. **Documenta los resultados** en tu tesis
2. **Captura screenshots** de las consultas exitosas
3. **Genera reportes** de diferentes cursos para análisis comparativo
4. **Prueba casos de uso reales** con preguntas de docentes/administradores

---

## Contacto

Si encuentras problemas, revisa:
- Logs de Neo4j: `logs/neo4j.log`
- Documentación del proyecto: `docs/GRAPHRAG_DOCUMENTATION.md`
- Pipeline semántico: `docs/SEMANTIC_PIPELINE_DOCUMENTATION.md`
