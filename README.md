# BootVFS

Monitor em Python de **possível** disponibilidade VFS Angola → Portugal. Abre a
página num Chromium real, procura textos configurados e alerta no terminal ou por
e-mail. Não reserva, não paga e não resolve CAPTCHA nem contorna filas ou bloqueios.

## Estado

Protótipo: a página pública de informações indicada não demonstra disponibilidade
do calendário. O acesso à VFS está bloqueado pelo proxy no ambiente de desenvolvimento.
Ainda é necessário observar o calendário real após login e configurar o URL, seletor
e textos de disponibilidade/indisponibilidade. Sem isso, o monitor recusa iniciar.
Não há integração de agendamento validada, nem garantia de obtenção de vaga.

## Instalação

Python 3.12 ou posterior:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
cp config.example.json config.json
```

Em Linux, se faltarem bibliotecas do navegador, instala-as com o procedimento
oficial `python -m playwright install-deps chromium` (requer permissões de sistema).
Para utilizar um Chromium já instalado, define `BOOTVFS_CHROMIUM` com o seu caminho.

## Preparar e executar

1. Abre a VFS manualmente, confirma as regras aplicáveis e entra na tua conta.
2. Em `config.json`, configura o URL oficial do calendário e um seletor CSS da
   área de disponibilidade. Preenche `available_text` e `unavailable_text` com
   frases completas **realmente observadas**. “Book an appointment” ou o botão
   para agendar não provam a existência de vagas. Não uses dados pessoais nas frases.
3. Num computador com ambiente gráfico, guarda a sessão:

   ```sh
   .venv/bin/python bootvfs.py --headed --login
   ```

4. Verifica uma vez e depois inicia o monitor:

   ```sh
   .venv/bin/python bootvfs.py --once
   .venv/bin/python bootvfs.py
   ```

O intervalo padrão é 15 minutos, com mínimo de 5 minutos. Falhas provocam espera
crescente e três verificações inconclusivas param o monitor. CAPTCHA, login e
fila identificados interrompem a execução para intervenção manual. Uma sessão
expirada não é uma vaga. O código de saída 2 indica verificação inconclusiva ou
intervenção necessária; 0 numa verificação única indica resultado reconhecido.

O alerta só reaparece após uma indisponibilidade reconhecida ou reinício do
processo. Uma possível vaga deve ser confirmada no site; finaliza o agendamento
manualmente. O monitor funciona apenas enquanto o processo estiver em execução.
Não o deixes a consultar páginas às quais não tens autorização de acesso.

## Alertas por e-mail (opcional)

O terminal está sempre ativo. Para receber também e-mail e WhatsApp:

```sh
.venv/bin/python bootvfs.py --channel email --channel whatsapp
```

Cada canal é tentado independentemente. Uma falha no e-mail não impede o WhatsApp.
Não há repetição automática de envios: verifica os erros no terminal. Após corrigir
as credenciais, reinicia o monitor para voltar a alertar uma possível vaga persistente.

Define `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` e `ALERT_TO` no ambiente do
processo, através de um gestor de segredos. `SMTP_PORT` é opcional (465, TLS).
Executa com `--channel email`. O envio ainda não foi validado contra um servidor
real. O programa não lê ficheiros `.env` automaticamente. Não coloques segredos
no código, no Git ou no chat. A rede precisa permitir o servidor SMTP por TCP.

A pasta `.bootvfs/` contém cookies que permitem aceder à tua sessão: mantém-na
privada, não a partilhes e apaga-a para remover a sessão local. Em ambientes cloud
partilhados, prefere iniciar sessão e executar o monitor no teu computador.

## WhatsApp (Meta Cloud API)

É necessário configurar WhatsApp Business/Cloud API na Meta, um número remetente
e um destinatário que tenha consentido em receber os alertas. Pode haver custos
da Meta. Não usa nem automatiza WhatsApp Web.

Cria um modelo aprovado, sem variáveis nem botões dinâmicos, com uma mensagem
como “Possível disponibilidade na VFS. Confirma no portal oficial e agenda
manualmente.” Inclui o link oficial como texto estático no modelo. Define no
ambiente do processo:

- `WHATSAPP_TOKEN`: token da Meta com permissão de envio.
- `WHATSAPP_PHONE_NUMBER_ID`: identificador do número remetente, não o telefone.
- `WHATSAPP_TO`: telefone destinatário em formato internacional, só dígitos.
- `WHATSAPP_TEMPLATE`: nome exato do modelo aprovado.
- `WHATSAPP_TEMPLATE_LANGUAGE`: código do idioma aprovado, por exemplo `pt_PT`.
- `WHATSAPP_API_VERSION`: versão suportada da Graph API no teu aplicativo Meta.

O envio usa HTTPS com verificação TLS para `graph.facebook.com`, que precisa estar
permitido na rede do ambiente. Não envies o token no chat. Se usares credenciais
por proxy, associa o token apenas a esse destino nas definições do ambiente.
Uma resposta de aceitação da API não garante entrega ao telefone. Os testes usam
respostas simuladas; nenhum e-mail ou WhatsApp real foi enviado ou validado.

## Desenvolvimento

```sh
.venv/bin/python -m unittest -v
.venv/bin/python browser_smoke.py
```

Os testes cobrem classificação conservadora e validação de configuração; não
validam disponibilidade na VFS. O smoke test abre duas páginas HTML locais no
Chromium e verifica a leitura dos estados. Neste ambiente foi validado com
`BOOTVFS_CHROMIUM=/usr/bin/chromium` e permissão do executor para abrir sockets.
Não existe serviço web nem servidor para iniciar.
