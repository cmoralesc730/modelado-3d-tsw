# repository.py
class MatrixRepository:
    def __init__(self):
        self._data: dict[int, dict] = {}
        self._next_id = 1

    def crear(self, matriz: dict) -> dict:
        matriz["id"] = self._next_id
        self._data[self._next_id] = matriz
        self._next_id += 1
        return matriz

    def obtener(self, id: int) -> dict | None:
        return self._data.get(id)

    def listar(self) -> list[dict]:
        return list(self._data.values())