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

![equation](https://latex.codecogs.com/svg.image?IC_{px}=\bar{px}\pm%20z\cdot\frac{\sigma_{px}}{\sqrt{n}})

![equation](https://latex.codecogs.com/svg.image?IC_{py}=\bar{py}\pm%20z\cdot\frac{\sigma_{py}}{\sqrt{n}})


- Se o intervalo é **estreito (alta confiança)** e o número de amostras é suficiente, assume-se que o campo é **posicionalmente estável**.
- Assim, é possível identificar diretamente o bloco correspondente **sem consultar o LLM**.

## 🔍 Como o Matching é Feito no Layout Memory

O método `layout_memory_search()` realiza o processo de correspondência (“matching”) entre os **campos esperados** e os **blocos de texto** do documento com base em duas heurísticas complementares: **posição** e **regex**.

### 1️⃣ Verificação de posição (Confidence Interval Matching)

Para cada campo definido no esquema (`schema`), o sistema recupera o **intervalo de confiança (IC)** das posições médias (`px`, `py`) armazenadas anteriormente.  
Esses valores representam onde, em média, aquele campo costuma aparecer no layout do documento.

O método procura entre os blocos (`blocks`) um cujo ponto (`px`, `py`) esteja dentro de um intervalo de confiançã **significativo**:

\[
IC_{px} = \bar{px} \pm z \cdot \frac{\sigma_{px}}{\sqrt{n}}
\]
\[
IC_{py} = \bar{py} \pm z \cdot \frac{\sigma_{py}}{\sqrt{n}}
\]

Se um bloco se encaixa nessa região, ele é considerado **candidato** para aquele campo.

---

### 2️⃣ Verificação de regex (Regex Matching)

Em seguida, o método busca no banco de dados se já existe um **regex aprendido** anteriormente para o campo.  
Caso exista, ele é aplicado sobre o texto do bloco candidato:

```python
regex_match = re.search(regex, block_data["text"], flags=re.MULTILINE)
```

Se o regex encontrar uma correspondência, o valor é extraído e o campo é adicionado a `llm_avoided_fields`, indicando que não foi necessário chamar o LLM para obtê-lo.

---

### 3️⃣ Fallback para o LLM

Se não for encontrado nenhum bloco candidato (fora do IC) ou o regex falhar, o campo é adicionado a `llm_fallback_fields`.  
Esses campos serão enviados ao modelo LLM, que extrairá o valor e poderá **gerar um novo regex** e **atualizar a posição média** daquele campo para futuras execuções.

---

Em resumo:
- **Posição →** garante que apenas blocos prováveis sejam testados.  
- **Regex →** valida o conteúdo textual dentro desses blocos.  
- **LLM →** é acionado apenas quando a heurística falha, alimentando novamente a memória.


Essa heurística reduz drasticamente o custo das inferências:
- Os primeiros documentos de cada tipo demandam chamadas custosas ao LLM (pois é necessário obter os regexes para os campos do documento);
- Após obtidos os regexes para os campos, o custo da chamada ao LLM reduz drasticamente, devido à complexidade envolvida na obtenção dos regexes.
- Após a obtenção da distribuição das posições dos blocos de texto do campo, podemos extrair os dados de forma **quase instantânea** para campos com elevado grau de regularidade em sua posição.

##### 🌐 Significância e decisão de fallback
O sistema classifica cada campo como:
- `high` → coordenadas altamente confiáveis (dispensa LLM);
- `medium` → coordenadas moderadamente estáveis (uso híbrido);
- `low` → instável, depende do LLM.

Observação: Vale salientar que, embora promissora, a abordagem é heurística e ainda demanda ajustes e testes empíricos 
para ajustar, sobretudo, a avaliação de hyperparâmetros para definir a significância do Intervalo de Confiança. Pretendo ainda explorar isso.

#### 4. **LLM Processor**
- Quando a memória de layout não é suficiente, o pipeline constrói um *prompt contextualizado* e envia ao LLM.
- O modelo retorna:
  - `valor` extraído
  - `regex` usado para encontrá-lo (Caso uma chamada anterior já não houver obtido o regex para o campo analisado)
  - `indice do bloco de origem` usado na atualização da media e variância do campo

#### 5. **Cache de resultados (document-level cache)**
Para acelerar ainda mais, há um **cache persistente para a tupla (texto do documento,label, campo)**:
- É gerado um *fingerprint SHA256*.
- Se uma requisição idêntica já foi processado, o resultado é retornado diretamente sem nova análise.

---

### 📉 Otimizações de Desempenho

| Técnica | Descrição | Impacto |
|----------|------------|---------|
| **Memória de Layout com IC** | Aprende posições médias e variação dos campos. | Reduz consultas ao LLM conforme o uso aumenta. |
| **Armazenamento incremental (Welford)** | Atualiza estatísticas sem reprocessar histórico. | Mantém desempenho estável e preciso. |
| **Cache de documentos (SHA256)** | Retorna resultados instantaneamente para PDFs já processados. | Evita recomputação e chamadas à API. |
| **LRU caching interno** | Minimiza acesso ao banco SQLite. | Diminui latência de consultas repetidas. |

💡 **Tendência natural de desempenho:**  
As primeiras requisições de um tipo de documento serão lentas (Extração de regexes pelo LLM é custusa), mas o sistema convergirá rapidamente para tempo de execução baixo conforme acumula conhecimento.

---

### 🧩 Exemplo de Fluxo Simplificado

1. Recebe PDF de Nota Fiscal (`label="nota_fiscal"`).  
2. LayoutMemory ainda vazio → tudo vai para o LLM.  
3. LLM retorna valores + regex + posições.  
4. Sistema atualiza memória com média, variância e regex.  
5. Eventualmente, após a população do LayoutMemory (Idealmente):  
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

## 🚀 Como Executar a Aplicação

### 🐳 Executando com Docker (recomendado)

A maneira mais simples de rodar a aplicação é usando o Docker.  
Basta garantir que você tenha o Docker instalado e executar os comandos abaixo:

```bash
# 1. Clone o repositório
git clone https://github.com/VictorGabrielMO/layout-aware-pdf-extractor.git
cd layout-aware-pdf-extractor

# 2. Crie a imagem Docker
docker build -t doc-extraction .

# 3. Rode o container
docker run -p 8000:8000 -e OPENAI_API_KEY=<sua_chave_openai> doc-extraction

```
Após a inicialização, basta acessar a **interface gráfica** em:  
👉 [http://localhost:8000](http://localhost:8000)

A interface permite enviar um PDF, informar o rótulo do documento e fornecer o esquema JSON para extração dos campos.

---

## 📡 Endpoint de Extração

Além da interface gráfica, a API também disponibiliza o endpoint:

```
POST /extract
```

### Parâmetros esperados (multipart/form-data)

| Campo        | Tipo         | Descrição |
|---------------|---------------|------------|
| `pdf`         | `file`        | Arquivo PDF a ser processado |
| `label`       | `string`      | Tipo de documento (ex: "nota_fiscal", "contrato") |
| `schema_json` | `string` (JSON) | Estrutura com os campos esperados e suas descrições |

### Exemplo de requisição `curl`:
```bash
curl -X POST http://localhost:8000/extract \
  -F "pdf=@exemplo.pdf" \
  -F "label=nota_fiscal" \
  -F 'schema_json={"CNPJ":"Número do CNPJ da empresa","Data":"Data de emissão"}'
```

### 📊 Considerações Finais

A principal proposta dessa solução é transformar o processo de extração de dados via LLM — tipicamente caro e lento — em um **sistema de aprendizado contínuo de layout**, com:
- Redução adaptativa de custo;
- Autoaprendizado de padrões;
- Independência crescente do modelo de linguagem.

Com o uso, o pipeline se comporta como um **extrator cognitivo especializado**, otimizando-se de forma autônoma com base nas interações anteriores.
