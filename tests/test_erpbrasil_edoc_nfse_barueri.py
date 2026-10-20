from types import SimpleNamespace
from unittest import TestCase

from erpbrasil.edoc.provedores.barueri import Barueri


def _msg(codigo, mensagem=None, correcao=None):
    return SimpleNamespace(Codigo=codigo, Mensagem=mensagem, Correcao=correcao)


def _processo(resposta, webservice="NFeLoteStatusArquivo"):
    return SimpleNamespace(webservice=webservice, resposta=resposta)


class TestBarueriRetornoConsulta(TestCase):
    """analisa_retorno_consulta so interpreta a resposta: nao precisa de
    bindings nem de transmissao, por isso o provedor e criado sem o __init__."""

    def setUp(self):
        self.barueri = Barueri.__new__(Barueri)

    def test_erro_sem_correcao_nao_quebra(self):
        """Correcao vazia estourava TypeError ao concatenar com None."""
        resposta = SimpleNamespace(
            ListaMensagemRetorno=_msg("E451", "RPS ja enviado"),
            ListaNfeArquivosRPS=None,
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertIsNone(status)
        self.assertEqual(mensagem, "E451 - RPS ja enviado\n")

    def test_erro_sem_mensagem_e_sem_correcao(self):
        resposta = SimpleNamespace(
            ListaMensagemRetorno=_msg("E999"), ListaNfeArquivosRPS=None
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertIsNone(status)
        self.assertEqual(mensagem, "E999\n")

    def test_erro_completo_mantem_o_formato_original(self):
        resposta = SimpleNamespace(
            ListaMensagemRetorno=_msg("E001", "Arquivo invalido", "Reenvie"),
            ListaNfeArquivosRPS=None,
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertIsNone(status)
        self.assertEqual(mensagem, "E001 - Arquivo invalido - Correção: Reenvie\n")

    def test_erros_em_container_mensagem_retorno(self):
        """O webservice devolve ListaMensagemRetorno.MensagemRetorno."""
        resposta = SimpleNamespace(
            ListaMensagemRetorno=SimpleNamespace(
                MensagemRetorno=[_msg("E451", "RPS ja enviado"), _msg("E452")]
            ),
            ListaNfeArquivosRPS=None,
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertIsNone(status)
        self.assertEqual(mensagem, "E451 - RPS ja enviado\nE452\n")

    def test_erros_em_lista(self):
        resposta = SimpleNamespace(
            ListaMensagemRetorno=[_msg("E451", "RPS ja enviado")],
            ListaNfeArquivosRPS=None,
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertIsNone(status)
        self.assertEqual(mensagem, "E451 - RPS ja enviado\n")

    def test_ok200_devolve_a_situacao_do_arquivo(self):
        for situacao, esperado in (
            (0, "Validated"),
            (1, "Successfully Processed"),
            (2, "Processed with Error"),
            (-1, "Batch not yet processed"),
            (-2, "Batch not yet processed"),
        ):
            with self.subTest(situacao=situacao):
                resposta = SimpleNamespace(
                    ListaMensagemRetorno=_msg("OK200"),
                    ListaNfeArquivosRPS=SimpleNamespace(SituacaoArq=str(situacao)),
                )
                status, mensagem = self.barueri.analisa_retorno_consulta(
                    _processo(resposta)
                )
                self.assertEqual(status, situacao)
                self.assertEqual(mensagem, esperado)

    def test_ok200_com_situacao_desconhecida(self):
        resposta = SimpleNamespace(
            ListaMensagemRetorno=_msg("OK200"),
            ListaNfeArquivosRPS=SimpleNamespace(SituacaoArq="7"),
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertEqual(status, 7)
        self.assertEqual(mensagem, "Situação desconhecida: 7")

    def test_ok200_sem_lista_de_arquivos(self):
        resposta = SimpleNamespace(
            ListaMensagemRetorno=_msg("OK200"), ListaNfeArquivosRPS=None
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertIsNone(status)
        self.assertEqual(mensagem, "")

    def test_sem_mensagem_de_retorno(self):
        resposta = SimpleNamespace(
            ListaMensagemRetorno=None,
            ListaNfeArquivosRPS=SimpleNamespace(SituacaoArq="0"),
        )
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(resposta))
        self.assertEqual(status, 0)
        self.assertEqual(mensagem, "Validated")

    def test_resposta_vazia(self):
        status, mensagem = self.barueri.analisa_retorno_consulta(_processo(None))
        self.assertIsNone(status)
        self.assertEqual(mensagem, "")

    def test_outro_servico_nao_e_interpretado(self):
        status, mensagem = self.barueri.analisa_retorno_consulta(
            _processo(SimpleNamespace(), webservice="NFeLoteEnviarArquivo")
        )
        self.assertIsNone(status)
        self.assertEqual(mensagem, "")
