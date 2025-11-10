# gpt2workout — Converter CSV em Treinos para Garmin, Zwift e MyWhoosh

O **gpt2workout** permite que você crie treinos conversando com o ChatGPT e converta o resultado para formatos utilizados por plataformas de ciclismo e dispositivos de treino.

Fluxo:
1. O atleta pede um treino ao ChatGPT em formato **CSV**.
2. O arquivo CSV é convertido usando este script.
3. O treino é importado para **Garmin**, **Zwift** e **MyWhoosh**.

```

## Recursos Principais

| Função | Formato | Observação |
|``````-|`````````|````````````|
| Exporta treino para Garmin | `.fit.csv` | Compatível com o **Garmin FIT SDK** |
| Gera treino Zwift / MyWhoosh | `.zwo` | Aceito por ambos (Workout Builder) |
| Gera arquivo `.fit` binário | `.fit` | Necessita do `FitCSVTool.jar` (opcional) |
| Suporte a potência, FC e cadência | ✅ | Potência em `%FTP` ou watts |
| Suporte a aquecimento / intervalos / recuperação / cooldown | ✅ | Treinos estruturados completos |

```

## Instalação

Requer **Python 3.8+**.

Clone o repositório:
```bash
git clone https://github.com/SEU_USUARIO/gpt2workout.git
cd gpt2workout
```

```

## Como Usar

Prepare o treino em CSV no formato:

```
workout_name,step_type,duration_type,duration_value,target_type,target_value,intensity,notes
```

### 1) Gerar `.fit.csv` (Garmin)
```bash
python csv2fit.py --in workout.csv --out meu_treino --sport cycling
```

### 2) Gerar `.zwo` (Zwift / MyWhoosh)
Se a potência for em **watts**, informe seu FTP:

```bash
python csv2fit.py --in workout.csv --out meu_treino --sport cycling --zwo --ftp 250
```

### 3) (Opcional) Gerar `.fit` completo
Baixe o FIT SDK da Garmin:
https://developer.garmin.com/fit/download/

Depois:
```bash
python csv2fit.py --in workout.csv --out meu_treino --sport cycling --fitcsvtool "/caminho/para/FitCSVTool.jar"
```

Ou conversão manual:
```bash
java -jar FitCSVTool.jar -c meu_treino.fit.csv meu_treino.fit
```

```

## Campos CSV Aceitos

| Coluna | Descrição |
|``````--|`````````--|
| `workout_name` | Nome do treino (igual em todas as linhas) |
| `step_type` | warmup, interval, recovery, cooldown |
| `duration_type` | `time` (segundos) ou `distance` (metros) |
| `duration_value` | Duração numérica |
| `target_type` | none, power, hr, cadence |
| `target_value` | Ex.: `95%-105%`, `200-260`, `Z2-Z3`, `90` |
| `intensity` | active ou rest |
| `notes` | Observações curtas |

```

## Exemplo de CSV

```
FTP Builder,warmup,time,600,power,55%-65%,active,Aquecer
FTP Builder,interval,time,480,power,95%-105%,active,Intervalo 1
FTP Builder,recovery,time,180,hr,Z1-Z2,rest,Recuperar
FTP Builder,interval,time,480,power,95%-105%,active,Intervalo 2
FTP Builder,recovery,time,180,hr,Z1-Z2,rest,Recuperar
FTP Builder,interval,time,480,power,95%-105%,active,Intervalo 3
FTP Builder,cooldown,time,600,none,,active,Desaquecimento
```

```

## Prompt Recomendado para Criar Treinos no ChatGPT

```
Você é meu treinador de ciclismo. Crie um treino estruturado apenas em formato CSV — sem explicações.

Cabeçalhos obrigatórios:
workout_name,step_type,duration_type,duration_value,target_type,target_value,intensity,notes

Regras:
- duration_type = time (segundos) ou distance (metros)
- target_type = power, hr, cadence ou none
- power pode ser %FTP (ex.: 85%-95%) ou watts
- hr pode ser bpm ou Zonas (Z2, Z3, etc.)
- Não inclua texto fora do CSV.

Objetivo: 1 hora para melhorar FTP, com aquecimento, 3-4 intervalos fortes, recuperação e cooldown.
```

```

## Licença
MIT

```

