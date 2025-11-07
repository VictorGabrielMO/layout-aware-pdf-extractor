## 🧩 Desafio de Extração de Informações de Documentos

Este projeto implementa uma **API de extração de informações de documentos PDF** utilizando **LLM (Large Language Models)**, com foco em **eficiência e reuso de conhecimento** através de uma **memória de layout persistente** e **cache de resultados**.

---

### 🚀 Visão Geral da Solução

O sistema é composto por um pipeline modular que processa PDFs e aprende progressivamente o layout dos documentos para reduzir drasticamente o tempo de execução em execuções subsequentes.  
A arquitetura foi desenhada para que o modelo de linguagem seja acionado **apenas quando estritamente necessário**, com base em **heurísticas estatísticas** e **armazenamento incremental de padrões (regexes)**.

---

### ⚙️ Pipeline de Processamento

A pipeline é composta pelas seguintes etapas principais:

#### 1. **Extração de texto e blocos (PDFParser)**
- O PDF é processado em duas representações:
  - Texto plano completo (`extract_plain_text`), usado para fingerprint e cache.
  - Blocos textuais estruturados (`extract_text_blocks`), contendo texto e coordenadas normalizadas (px, py).
- Essa granularidade permite análises espaciais precisas no layout.

#### 2. **Pré-processamento dos blocos (Preprocessor)**
- Os blocos são limpos e normalizados (remoção de ruído, quebras e padrões redundantes).
- A saída é uma lista de blocos prontos para serem analisados pela heurística de layout.

#### 3. **Memória de Layout (LayoutMemory)**
Essa é a **camada central de inteligência** da solução.

- Cada campo de cada tipo de documento é armazenado com:
  - As **coordenadas médias (px, py)** em que o campo aparece.
  - As **variâncias acumuladas (M2_px, M2_py)**.
  - Um **regex aprendido** pelo LLM, usado para extrações diretas futuras.
- Os valores são atualizados incrementalmente com o **algoritmo de Welford**, o que garante médias e variâncias corretas sem reprocessar o histórico.

##### 🧠 Heurística de Intervalo de Confiança (CI)
Para cada campo, é calculado um **intervalo de confiança (IC)** das posições:

\[
IC_{px} = \bar{px} \pm z \cdot \frac{\sigma_{px}}{\sqrt{n}}
\]
\[
IC_{py} = \bar{py} \pm z \cdot \frac{\sigma_{py}}{\sqrt{n}}
\]

- Se o intervalo é **estreito (alta confiança)** e o número de amostras é suficiente, assume-se que o campo é **posicionalmente estável**.
- Assim, é possível identificar diretamente o bloco correspondente **sem consultar o LLM**.

Essa heurística reduz drasticamente o custo das inferências:
- Os primeiros documentos de cada tipo demandam chamadas ao LLM (pois é necessário aprender os regexes e coordenadas);
- As execuções seguintes reutilizam o conhecimento armazenado, tornando o processo **quase instantâneo**.

##### 🌐 Significância e decisão de fallback
O sistema classifica cada campo como:
- `high` → coordenadas altamente confiáveis (dispensa LLM);
- `medium` → coordenadas moderadamente estáveis (uso híbrido);
- `low` → instável, depende do LLM.

#### 4. **LLM Processor**
- Quando a memória de layout não é suficiente, o pipeline constrói um *prompt contextualizado* e envia ao LLM.
- O modelo retorna:
  - `valor` extraído
  - `regex` usado para encontrá-lo
  - `bloco` de origem
- O regex e posição são armazenados na memória para futuros usos.

#### 5. **Cache de resultados (document-level cache)**
Para acelerar ainda mais, há um **cache persistente por documento e schema**:
- É gerado um *fingerprint SHA256* do texto e schema.
- Se um documento idêntico já foi processado, o resultado é retornado diretamente sem nova análise.

---

### 📉 Otimizações de Desempenho

| Técnica | Descrição | Impacto |
|----------|------------|---------|
| **Memória de Layout com IC** | Aprende posições médias e variação dos campos. | Reduz consultas ao LLM conforme o uso aumenta. |
| **Armazenamento incremental (Welford)** | Atualiza estatísticas sem reprocessar histórico. | Mantém desempenho estável e preciso. |
| **Cache de documentos (SHA256)** | Retorna resultados instantaneamente para PDFs já processados. | Evita recomputação e chamadas à API. |
| **LRU caching interno** | Minimiza acesso ao banco SQLite. | Diminui latência de consultas repetidas. |

💡 **Tendência natural de desempenho:**  
As primeiras requisições de um tipo de documento serão lentas (dependência do LLM), mas o sistema convergirá rapidamente para tempo de execução muito baixo conforme acumula conhecimento.

---

### 🧩 Exemplo de Fluxo Simplificado

1. Recebe PDF de Nota Fiscal (`label="nota_fiscal"`).  
2. LayoutMemory ainda vazio → tudo vai para o LLM.  
3. LLM retorna valores + regex + posições.  
4. Sistema atualiza memória com média, variância e regex.  
5. Próximos documentos similares:  
   - Blocos são casados via IC e regex.  
   - Somente campos não encontrados vão ao LLM.  

Resultado: **redução progressiva do custo por documento.**

---

### 🧰 Tecnologias Utilizadas

- **FastAPI** — backend e endpoint `/extract`
- **SQLite** — armazenamento leve e persistente da memória de layout
- **OpenAI API** — processamento de linguagem natural e aprendizado de padrões
- **Pydantic** — validação de entrada e saída
- **Docker** — empacotamento e execução isolada

---

### 📊 Considerações Finais

A principal proposta dessa solução é transformar o processo de extração de dados via LLM — tipicamente caro e lento — em um **sistema de aprendizado contínuo de layout**, com:
- Redução adaptativa de custo;
- Autoaprendizado de padrões;
- Independência crescente do modelo de linguagem.

Com o uso, o pipeline se comporta como um **extrator cognitivo especializado**, otimizando-se de forma autônoma com base nas interações anteriores.
