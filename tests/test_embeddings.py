import numpy as np
import pytest

from verdade_ou_fake.config import Config
from verdade_ou_fake.embeddings import criar_embutidor


@pytest.mark.rede
def test_embeddings_tem_norma_um_e_aproximam_traducoes():
    embutir = criar_embutidor(Config().modelo_embedding)
    textos = [
        "O alho cura a hipertensão arterial",
        "Garlic cures high blood pressure",
        "The stock market closed higher on Tuesday",
    ]
    vetores = embutir(textos)

    assert vetores.shape[0] == 3
    assert vetores.shape[1] > 1
    assert vetores.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(vetores, axis=1), 1.0, atol=1e-5)
    assert vetores[0] @ vetores[1] > vetores[0] @ vetores[2]
