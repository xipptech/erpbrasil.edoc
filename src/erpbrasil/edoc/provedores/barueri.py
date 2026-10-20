# Copyright (C) 2023  Luis Felipe Mileo - KMEE


from erpbrasil.edoc.nfse import NFSe, ServicoNFSe
from erpbrasil.edoc.resposta import RetornoSoap

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin

try:
    from nfselib.barueri import (
        NFeLoteBaixarArquivo,
        NFeLoteEnviarArquivo,
        NFeLoteStatusArquivo,
    )

    barueri = True
except ImportError:
    barueri = False

endpoint = "nfeservice/wsrps.asmx?WSDL"

SITUACOES_ARQUIVO = {
    0: "Validated",
    1: "Successfully Processed",
    2: "Processed with Error",
    -1: "Batch not yet processed",
    -2: "Batch not yet processed",
}

if barueri:
    servicos = {
        "envia_documento": ServicoNFSe(
            "NFeLoteEnviarArquivo", endpoint, NFeLoteEnviarArquivo, True
        ),
        "consulta_recibo": ServicoNFSe(
            "NFeLoteStatusArquivo", endpoint, NFeLoteStatusArquivo, True
        ),
        "consultar_lote_rps": ServicoNFSe(
            "NFeLoteStatusArquivo", endpoint, NFeLoteStatusArquivo, True
        ),
        "baixar_lote_rps": ServicoNFSe(
            "NFeLoteBaixarArquivo", endpoint, NFeLoteBaixarArquivo, True
        ),
        "consulta_nfse_rps": ServicoNFSe(
            "NFeLoteStatusArquivo", endpoint, NFeLoteStatusArquivo, True
        ),
    }
else:
    servicos = {}
    cabecalho = None


class Barueri(NFSe):
    def __init__(
        self, transmissao, ambiente, cidade_ibge, cnpj_prestador, im_prestador
    ):
        if ambiente == "2":
            self._url = "https://testeeiss.barueri.sp.gov.br/"
        else:
            self._url = "https://www.barueri.sp.gov.br/"
        self._servicos = servicos

        super().__init__(
            transmissao, ambiente, cidade_ibge, cnpj_prestador, im_prestador
        )

    def get_documento_id(self, edoc):
        # edoc.LoteRps.ListaRps.Rps[0].InfRps.Id
        return edoc.LoteRps.Id, edoc.LoteRps.NumeroLote

    def _prepara_envia_documento(self, edoc):
        xml_string, xml_etree = self._generateds_to_string_etree(edoc)
        return xml_string

    def _prepara_consulta_recibo(self, proc_envio):
        raiz = NFeLoteStatusArquivo.NFeLoteStatusArquivo(
            CPFCNPJContrib=self.cnpj_prestador,
            InscricaoMunicipal=self.im_prestador,
            ProtocoloRemessa=proc_envio.resposta.ProtocoloRemessa,
        )
        return raiz

    def _prepara_consultar_lote_rps(self, protocolo):
        raiz = NFeLoteStatusArquivo.NFeLoteStatusArquivo(
            CPFCNPJContrib=self.cnpj_prestador,
            InscricaoMunicipal=self.im_prestador,
            ProtocoloRemessa=protocolo,
        )
        return raiz

    def _prepara_baixar_lote_rps(self, nome_arq_retorno):
        raiz = NFeLoteBaixarArquivo.NFeLoteBaixarArquivo(
            CPFCNPJContrib=self.cnpj_prestador,
            InscricaoMunicipal=self.im_prestador,
            NomeArqRetorno=nome_arq_retorno,
        )
        return raiz

    def baixar_lote_rps(self, protocolo=None):
        return self._post(
            body=self._prepara_baixar_lote_rps(protocolo),
            servico=self._servicos[self.baixar_lote_rps.__name__],
        )

    def _verifica_resposta_envio_sucesso(self, proc_envio):
        if proc_envio.retorno.ProtocoloRemessa:
            return True
        return False

    def _edoc_situacao_em_processamento(self, proc_recibo):
        return proc_recibo.retorno.ListaNfeArquivosRPS.SituacaoArq == 2

    def _prepara_cancelar_nfse_envio(self, doc_numero):
        pass

    def _prepara_consultar_nfse_rps(self, **kwargs):
        protocolo = kwargs.get("lot_receipt_number")
        raiz = NFeLoteStatusArquivo.NFeLoteStatusArquivo(
            CPFCNPJContrib=self.cnpj_prestador,
            InscricaoMunicipal=self.im_prestador,
            ProtocoloRemessa=protocolo,
        )
        return raiz

    @staticmethod
    def _mensagens_retorno(resposta):
        """Normaliza ListaMensagemRetorno, que vem como container com
        .MensagemRetorno, como lista ou como mensagem unica."""
        lista_msgs = getattr(resposta, "ListaMensagemRetorno", None)
        lista_msgs = getattr(lista_msgs, "MensagemRetorno", lista_msgs)
        if lista_msgs is None:
            return []
        if not isinstance(lista_msgs, list):
            return [lista_msgs]
        return lista_msgs

    @staticmethod
    def _formata_mensagem_retorno(msg):
        """Monta o texto da mensagem ignorando os campos nao preenchidos:
        Mensagem e Correcao sao opcionais no retorno do webservice."""
        texto = " - ".join([campo for campo in (msg.Codigo, msg.Mensagem) if campo])
        if msg.Correcao:
            texto += " - Correção: " + msg.Correcao
        return texto

    def analisa_retorno_consulta(self, processo):
        status = None
        mensagem = ""

        if processo.webservice != "NFeLoteStatusArquivo" or not processo.resposta:
            return status, mensagem

        erros = [
            msg
            for msg in self._mensagens_retorno(processo.resposta)
            if msg.Codigo != "OK200"
        ]
        if erros:
            mensagem = "".join(
                [self._formata_mensagem_retorno(msg) + "\n" for msg in erros]
            )
            return status, mensagem

        arquivos = getattr(processo.resposta, "ListaNfeArquivosRPS", None)
        situacao = getattr(arquivos, "SituacaoArq", None)
        if situacao is None:
            return status, mensagem

        status = int(situacao)
        mensagem = SITUACOES_ARQUIVO.get(status, f"Situação desconhecida: {status}")

        return status, mensagem

    def analisa_retorno_cancelamento(self, processo):
        pass

    def _post(self, body, servico):
        header_string = "1"

        body_string, body_etree = self._generateds_to_string_etree(body)

        if servico.operacao == "ConsultaNFeRecebidaNumero":
            self._url = "https://servicos.barueri.sp.gov.br"

        if header_string:
            with self._transmissao.cliente(
                urljoin(self._url, servico.endpoint)
            ) as cliente:
                resposta = cliente.service[servico.operacao](
                    header_string,
                    body_string,
                )
        else:
            with self._transmissao.cliente(
                urljoin(self._url, servico.endpoint)
            ) as cliente:
                resposta = cliente.service[servico.operacao](
                    body_string,
                )

        return self.analisar_retorno(
            servico.operacao, body, body_string, resposta, servico.classe_retorno
        )

    def analisar_retorno(self, operacao, raiz, xml, retorno, classe):
        resposta = False
        if retorno:
            classe.Validate_simpletypes_ = False
            # resultado = etree.tostring(etree.fromstring(retorno.encode("utf-8")))
            # resposta = classe.parseString(resultado, silence=True)
            resposta = retorno
        return RetornoSoap(operacao, raiz, xml, retorno, resposta)
