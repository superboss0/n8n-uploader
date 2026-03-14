from counterparty_transform import transform_excel_bytes
from processors.registry import registry


registry.register(
    "counterparty_transform",
    transform_excel_bytes,
    label="Преобразование отчета FinGrad",
    description="Преобразует отчет балансов контрагентов в нормализованный Excel.",
)
