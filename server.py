import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
from datetime import date as date_type, datetime, timedelta, timezone
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
DB_PATH = Path(os.environ.get("RYD_DB_PATH", ROOT / "data" / "ryd.db"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
SESSION_DAYS = 30
STUDY_QUIZ_VERSION = 2
STUDY_PLAN_START = date_type(2026, 7, 13)
STUDY_PLAN_END = date_type(2027, 6, 1)

STUDY_QUIZZES = {
    "module9": [
        ("Как называется точка, представляющая центр кластера в k-means?", ("центроид", "центр кластера"), "На шаге обновления k-means пересчитывает центроиды."),
        ("Какую норму использует стандартный k-means: L1 или квадрат L2?", ("l2", "квадрат l2", "евклидову", "евклидово расстояние"), "Функция потерь k-means основана на квадратах евклидовых расстояний."),
        ("Почему перед k-means обычно масштабируют признаки?", ("чтобы признаки были одного масштаба", "из-за масштаба признаков", "чтобы масштаб не влиял на расстояние"), "Признак с большим масштабом иначе доминирует в расстоянии."),
        ("Как называется метод инициализации центроидов, используемый sklearn по умолчанию?", ("k-means++", "kmeans++"), "k-means++ разносит начальные центры и обычно улучшает результат."),
        ("Какое преобразование данных обязательно перед PCA?", ("центрирование", "центрировать", "вычесть среднее"), "PCA применяют к центрированным данным."),
        ("Что максимизирует первая главная компонента?", ("дисперсию", "variance", "вариацию"), "Первая компонента выбирает направление максимальной дисперсии."),
        ("Как называются направления главных компонент в терминах ковариационной матрицы?", ("собственные векторы", "собственные вектора"), "Главные направления задаются собственными векторами ковариационной матрицы."),
        ("Является ли k-means устойчивым к выбросам: да или нет?", ("нет",), "Среднее и квадраты расстояний делают k-means чувствительным к выбросам."),
        ("Как называется сумма квадратов расстояний объектов до центроидов?", ("inertia", "инерция", "within-cluster sum of squares", "wcss"), "В sklearn эта величина доступна как inertia_."),
        ("Можно ли напрямую считать номер кластера истинным классом: да или нет?", ("нет",), "Номера кластеров условны, а кластеризация не использует истинные метки."),
    ],
    "module10": [
        ("Как называется вектор из частных производных функции?", ("градиент",), "Градиент указывает направление быстрейшего роста функции."),
        ("Куда направлен шаг градиентного спуска: по градиенту или против него?", ("против", "против градиента", "в минус градиент"), "Для минимизации двигаются в направлении минус градиента."),
        ("Что чаще всего происходит при слишком большом learning rate?", ("расходимость", "модель расходится", "перескакивание минимума"), "Шаги могут перескакивать минимум, и оптимизация расходится."),
        ("Достаточно ли равенства производной нулю, чтобы точка была минимумом: да или нет?", ("нет",), "Это может быть максимум или седловая точка; нужны дополнительные условия."),
        ("Как называется функция, у которой отрезок между двумя точками лежит не ниже графика?", ("выпуклая", "выпуклая функция"), "Для выпуклой функции локальный минимум является глобальным."),
        ("Чему равна производная x в квадрате?", ("2x", "2*x"), "По степенному правилу производная x² равна 2x."),
        ("Как называется параметр размера шага градиентного спуска?", ("learning rate", "скорость обучения", "шаг обучения"), "Learning rate определяет длину шага оптимизации."),
        ("Какой знак ставят перед learning rate в формуле градиентного спуска?", ("минус", "-"), "Из параметров вычитают learning rate, умноженный на градиент."),
        ("Как называется производная функции нескольких переменных по одной переменной?", ("частная производная", "частная"), "Градиент состоит из частных производных."),
        ("Что ищет задача минимизации: аргумент или только значение функции?", ("аргумент", "argmin"), "argmin возвращает точку, в которой достигается минимальное значение."),
    ],
    "foundation": [
        ("Сколько столбцов будет у произведения матриц размеров 3x4 и 4x2?", ("2",), "Произведение имеет размер 3x2."),
        ("Как называется максимальное число линейно независимых строк или столбцов матрицы?", ("ранг", "rank"), "Это ранг матрицы."),
        ("Какое предварительное преобразование данных обязательно перед PCA?", ("центрирование", "центрировать", "вычесть среднее"), "PCA применяют к центрированным данным."),
        ("Как называется точка, представляющая центр кластера в k-means?", ("центроид", "центр кластера"), "На шаге обновления k-means пересчитывает центроиды."),
        ("Какую норму обычно минимизирует k-means: L1 или квадрат L2?", ("l2", "квадрат l2", "евклидову", "евклидово расстояние"), "Функция потерь k-means основана на квадратах евклидовых расстояний."),
        ("Чему равен скалярный продукт ортогональных векторов?", ("0", "нулю"), "У перпендикулярных векторов скалярное произведение равно нулю."),
        ("Как называется вектор из частных производных функции?", ("градиент",), "Градиент указывает направление быстрейшего роста функции."),
        ("Куда направлен шаг градиентного спуска: по градиенту или против него?", ("против", "против градиента", "в минус градиент"), "Для минимизации двигаются в направлении минус градиента."),
        ("Что чаще всего происходит при слишком большом learning rate?", ("расходимость", "модель расходится", "перескакивание минимума"), "Шаги могут перескакивать минимум, и оптимизация расходится."),
        ("Как называется число lambda в равенстве Av = lambda*v?", ("собственное значение", "собственное число"), "Lambda является собственным значением матрицы A."),
    ],
    "validation": [
        ("Как называется попадание информации из test в обучение?", ("утечка", "утечка данных", "data leakage", "leakage"), "Это утечка данных, делающая оценку завышенной."),
        ("Какой split сохраняет доли классов?", ("stratified", "стратифицированный", "stratified split"), "Stratified split сохраняет пропорции классов."),
        ("Какой split нужен, если строки одного пользователя не должны попасть в разные выборки?", ("group", "group split", "групповой"), "Используют group split по идентификатору пользователя."),
        ("Какая метрика объединяет precision и recall гармоническим средним?", ("f1", "f1-score", "f1 score"), "Это F1-score."),
        ("Что предпочтительнее при сильном дисбалансе и редком положительном классе: ROC-AUC или PR-AUC?", ("pr-auc", "pr auc", "prauc"), "PR-AUC лучше отражает качество на редком положительном классе."),
        ("Как называется доля найденных положительных объектов среди всех реальных положительных?", ("recall", "полнота"), "Это recall, или полнота."),
        ("Как называется доля верных положительных прогнозов среди всех положительных прогнозов?", ("precision", "точность"), "Это precision."),
        ("Какую ошибку сильнее штрафует RMSE по сравнению с MAE?", ("большую", "большие ошибки", "выбросы"), "Из-за квадрата RMSE сильнее реагирует на крупные ошибки."),
        ("На какой выборке окончательно оценивают выбранную модель?", ("test", "тестовой", "тестовая"), "Test используют один раз для итоговой оценки."),
        ("Какой вид валидации нужен для данных, упорядоченных по времени?", ("time-series split", "time series split", "временной", "по времени"), "Будущее не должно попадать в обучение для прошлого."),
    ],
    "models": [
        ("Как называется простая модель, с которой сравнивают улучшения?", ("baseline", "бейслайн"), "Сначала фиксируют baseline."),
        ("Какой объект sklearn объединяет preprocessing и модель без утечки?", ("pipeline", "пайплайн"), "Pipeline применяет преобразования внутри каждого split."),
        ("Какой метод PyTorch вычисляет градиенты?", ("backward", "backward()"), "Обычно вызывают loss.backward()."),
        ("Какой метод оптимизатора обновляет веса?", ("step", "step()", "optimizer.step()"), "optimizer.step() применяет вычисленные градиенты."),
        ("Что нужно вызвать перед новым backward, чтобы очистить прошлые градиенты?", ("zero_grad", "zero_grad()", "optimizer.zero_grad()"), "В PyTorch градиенты накапливаются, поэтому их обнуляют."),
        ("Какой режим включает model.eval()?", ("оценки", "валидации", "инференса", "evaluation"), "eval переключает слои в режим оценки."),
        ("Как называется подбор параметров модели по validation?", ("подбор гиперпараметров", "тюнинг", "hyperparameter tuning"), "Параметры выбирают по validation, не по test."),
        ("Какая асимптотика у классического бинарного поиска?", ("o(log n)", "log n", "логарифмическая"), "На каждом шаге область поиска делится пополам."),
        ("Как называется сохранение промежуточных ответов в динамическом программировании?", ("мемоизация", "memoization"), "Мемоизация не позволяет пересчитывать одинаковые состояния."),
        ("Какой алгоритм обхода графа использует очередь: BFS или DFS?", ("bfs", "поиск в ширину"), "BFS обрабатывает вершины по слоям через очередь."),
    ],
    "nlp": [
        ("Как называется разбиение текста на элементы словаря модели?", ("токенизация", "tokenization"), "Токенизация преобразует текст в последовательность токенов."),
        ("Какая маска скрывает padding от attention?", ("attention mask", "attention_mask", "маска внимания"), "Attention mask отмечает реальные токены и padding."),
        ("Какая классическая модель признаков взвешивает слова по частоте в документе и корпусе?", ("tf-idf", "tfidf"), "TF-IDF является сильным текстовым baseline."),
        ("Как называется сходство, основанное на угле между эмбеддингами?", ("cosine similarity", "косинусное сходство", "косинусная близость"), "Cosine similarity сравнивает направления векторов."),
        ("Какие три матрицы используются в self-attention?", ("q k v", "q, k, v", "query key value", "query, key, value"), "Self-attention строится на Query, Key и Value."),
        ("Какой блок Transformer обычно двунаправленно кодирует вход: encoder или decoder?", ("encoder", "энкодер"), "Encoder видит контекст с обеих сторон без causal mask."),
        ("К какому типу моделей относится BERT: encoder или decoder?", ("encoder", "энкодер", "encoder-like"), "BERT является encoder-like моделью."),
        ("Как называется дообучение всех весов готовой модели?", ("fine-tuning", "fine tuning", "файнтюнинг"), "При fine-tuning обновляются веса предобученной модели."),
        ("Что делает causal mask в decoder?", ("скрывает будущие токены", "запрещает смотреть в будущее", "маскирует будущие токены"), "Токен не должен получать информацию из будущих позиций."),
        ("Какой слой переводит id токена в плотный вектор?", ("embedding", "эмбеддинг", "embedding layer"), "Embedding layer сопоставляет индексу обучаемый вектор."),
    ],
    "applied": [
        ("Как называется поиск ближайших документов по эмбеддингу запроса?", ("semantic search", "семантический поиск", "vector search", "векторный поиск"), "Это semantic/vector search."),
        ("Какая retrieval-метрика показывает, найден ли релевантный документ в первых k результатах?", ("recall@k", "recall at k"), "Recall@k измеряет полноту выдачи до позиции k."),
        ("Как называется повторная сортировка кандидатов более точной моделью?", ("reranking", "реранжирование"), "Reranker уточняет порядок документов после retrieval."),
        ("Как называется разбиение документа на фрагменты для RAG?", ("chunking", "чанкинг"), "Chunking определяет единицы индексирования и retrieval."),
        ("Как называется изменение распределения входных данных со временем?", ("data drift", "дрейф данных"), "Data drift нужно отслеживать после запуска модели."),
        ("Как называется компромисс между недообучением и переобучением?", ("bias-variance", "bias variance", "смещение-дисперсия"), "Это bias-variance trade-off."),
        ("Что должно быть зафиксировано для воспроизводимого случайного эксперимента?", ("seed", "random seed", "случайное зерно"), "Фиксированный seed помогает повторить split и обучение."),
        ("Как называется анализ примеров, на которых модель ошиблась?", ("error analysis", "анализ ошибок"), "Error analysis определяет направления следующих экспериментов."),
        ("Как называется самый простой рабочий вариант решения?", ("baseline", "бейслайн"), "Baseline показывает, дают ли сложные эксперименты улучшение."),
        ("Какой SQL-оператор вычисляет значение по условию?", ("case when", "case"), "CASE WHEN реализует условную логику в SQL."),
    ],
    "interview": [
        ("Как называется метрика, непосредственно связанная с целью продукта?", ("бизнес-метрика", "business metric"), "Техническую метрику выбирают с учетом бизнес-метрики."),
        ("Как называется запуск модели на группе объектов по расписанию?", ("batch inference", "batch", "пакетный инференс"), "Batch inference обрабатывает накопившуюся партию."),
        ("Как называется выдача прогноза сразу по запросу пользователя?", ("online inference", "online", "онлайн инференс"), "Online inference требует низкой задержки."),
        ("Какой файл обычно описывает запуск и устройство проекта на GitHub?", ("readme", "readme.md"), "README должен содержать постановку, запуск и результаты."),
        ("Как называется проверка кандидата на реальном бизнес-сценарии без готовой формулы?", ("ml case", "ml-case", "ml кейс"), "ML-case проверяет постановку задачи и выбор решения."),
        ("Что нельзя использовать для выбора лучшего эксперимента: validation или test?", ("test", "тест", "тестовую выборку"), "Иначе итоговая оценка становится смещенной."),
        ("Как называется наблюдение за качеством модели после запуска?", ("мониторинг", "monitoring"), "Мониторинг отслеживает качество, задержки и drift."),
        ("Как называется статистически значимое изменение распределения признаков?", ("data drift", "дрейф данных"), "Data drift может ухудшить модель даже без изменения кода."),
        ("Как называется ограниченная версия продукта для проверки гипотезы?", ("mvp", "minimum viable product"), "MVP позволяет проверить ценность до сложной реализации."),
        ("Что нужно назвать после результата проекта: только успехи или также ограничения?", ("ограничения", "также ограничения", "limitations"), "Честный рассказ включает ошибки и ограничения решения."),
    ],
}

COURSE_MODULE_QUIZZES = {
    11: [("Как расшифровывается EDA?", ("exploratory data analysis", "разведочный анализ данных"), "EDA — разведочный анализ данных."), ("Как называется аномально далекое наблюдение?", ("выброс", "outlier"), "Это выброс."), ("Можно ли заполнять пропуски до разделения данных: да или нет?", ("нет",), "Иначе статистики заполнения могут вызвать утечку.")],
    12: [("Какой вердикт означает превышение времени?", ("tle",), "TLE — Time Limit Exceeded."), ("Какая сложность у одного прохода по массиву?", ("o(n)", "n", "линейная"), "Один проход имеет линейную сложность."), ("Какая структура хранит пары ключ-значение?", ("словарь", "dict", "hash map", "хеш-таблица"), "Для этого используют словарь или hash map.")],
    13: [("Какая метрика объединяет precision и recall?", ("f1", "f1-score"), "F1 является их гармоническим средним."), ("Какая метрика регрессии измеряется в единицах целевой переменной: MSE или RMSE?", ("rmse",), "После извлечения корня RMSE возвращается к исходным единицам."), ("Как называется доля найденных положительных объектов?", ("recall", "полнота"), "Это recall.")],
    14: [("Чему равен скалярный продукт ортогональных векторов?", ("0", "нулю"), "Он равен нулю."), ("Как называется длина вектора?", ("норма",), "Длину вектора задает норма."), ("Как называется максимальное число линейно независимых строк матрицы?", ("ранг",), "Это ранг матрицы.")],
    15: [("Как называется попадание test-информации в обучение?", ("утечка", "leakage", "data leakage"), "Это утечка данных."), ("Какой split сохраняет доли классов?", ("stratified", "стратифицированный"), "Используют stratified split."), ("Можно ли выбирать модель по test: да или нет?", ("нет",), "Модель выбирают по validation.")],
    16: [("Какая сложность у бинарного поиска?", ("o(log n)", "log n", "логарифмическая"), "Диапазон делится пополам."), ("Должны ли данные быть упорядочены для обычного бинарного поиска?", ("да",), "Обычный бинарный поиск требует монотонного порядка."), ("Как называется поиск минимального подходящего значения через монотонный предикат?", ("бинарный поиск по ответу",), "Это бинарный поиск по ответу.")],
    17: [("Как называется простая модель для сравнения?", ("baseline", "бейслайн"), "Сначала фиксируют baseline."), ("Какой объект sklearn объединяет preprocessing и модель?", ("pipeline", "пайплайн"), "Pipeline предотвращает утечки преобразований."), ("На какой выборке подбирают гиперпараметры?", ("validation", "валидационной", "валидация"), "Не на test.")],
    18: [("Как называется сохранение ответов подзадач?", ("мемоизация", "memoization"), "Мемоизация исключает повторные вычисления."), ("Какая техника хранит суммы первых k элементов?", ("префиксные суммы", "prefix sums"), "Это префиксные суммы."), ("Сколько индексов двигает техника two pointers?", ("2", "два"), "Она использует два указателя.")],
    19: [("Какой метод PyTorch вычисляет градиенты?", ("backward", "backward()"), "Вызывают loss.backward()."), ("Что делает optimizer.step()?", ("обновляет веса", "обновляет параметры"), "Он применяет градиенты к параметрам."), ("Как называется нелинейная функция между слоями?", ("функция активации", "activation"), "Без активаций сеть остается линейной.")],
    20: [("Какой обход графа использует очередь?", ("bfs", "поиск в ширину"), "BFS использует очередь."), ("Какой обход обычно реализуют рекурсией или стеком?", ("dfs", "поиск в глубину"), "DFS идет в глубину."), ("Как называется список соседей каждой вершины?", ("список смежности",), "Это список смежности.")],
    21: [("Как называется операция с ядром по изображению?", ("свертка", "convolution"), "Это свертка."), ("Как называется дообучение готовой модели?", ("fine-tuning", "файнтюнинг"), "Это fine-tuning."), ("Какой слой уменьшает пространственный размер карты признаков?", ("pooling", "пулинг"), "Pooling агрегирует локальные области.")],
    22: [("Какой алгоритм ищет кратчайшие пути при неотрицательных весах?", ("дейкстра", "dijkstra"), "Это алгоритм Дейкстры."), ("Какой алгоритм находит пути между всеми парами вершин?", ("флойд-уоршелл", "флойд", "floyd-warshall"), "Это Floyd–Warshall."), ("Как называется расстояние по числу вставок, удалений и замен?", ("расстояние левенштейна", "левенштейн"), "Это расстояние Левенштейна.")],
    23: [("Из каких двух частей состоит автоэнкодер?", ("энкодер и декодер", "encoder decoder", "encoder и decoder"), "Encoder сжимает, decoder восстанавливает."), ("Что является целевой переменной обычного автоэнкодера?", ("вход", "исходные данные", "x"), "Модель восстанавливает собственный вход."), ("Как называется сжатое представление между encoder и decoder?", ("латентное представление", "latent", "латентный вектор"), "Это latent representation.")],
    24: [("Сколько подмножеств у множества из n элементов?", ("2^n", "2 в степени n"), "Каждый элемент включается или нет."), ("Как называется представление подмножества целым числом?", ("битовая маска", "bitmask"), "Это битовая маска."), ("На сколько частей делит диапазон тернарный поиск?", ("3", "три"), "Он сравнивает две точки и отбрасывает одну из трех частей.")],
    25: [("Как называется разбиение текста на элементы словаря?", ("токенизация",), "Это токенизация."), ("Какая модель признаков использует частоту слова и обратную частоту документа?", ("tf-idf", "tfidf"), "Это TF-IDF."), ("Как называется плотный вектор слова?", ("эмбеддинг", "embedding"), "Это embedding.")],
    26: [("Как называется вероятностный метод со случайными испытаниями?", ("монте-карло", "monte carlo"), "Это Monte Carlo."), ("Как называется оптимизация с постепенным снижением температуры?", ("имитация отжига", "simulated annealing", "отжиг"), "Это simulated annealing."), ("Как называется поиск, сохраняющий ограниченное число лучших кандидатов?", ("beam search", "лучевой поиск"), "Это beam search.")],
    27: [("Какие сети обрабатывают последовательность рекуррентно?", ("rnn", "рекуррентные нейронные сети"), "Это RNN."), ("Какие три матрицы используются в attention?", ("q k v", "q, k, v", "query key value"), "Это Query, Key и Value."), ("Как называется предсказание следующего токена?", ("языковое моделирование", "language modeling"), "Это задача language modeling.")],
    28: [("К какому типу относится BERT: encoder или decoder?", ("encoder", "энкодер"), "BERT — encoder-like модель."), ("Что запрещает смотреть на будущие токены?", ("causal mask", "каузальная маска"), "Causal mask используется в decoder."), ("Как называется механизм связей всех токенов друг с другом?", ("self-attention", "самовнимание"), "Это self-attention.")],
    29: [("Как расшифровывается ViT?", ("vision transformer",), "ViT — Vision Transformer."), ("Какая модель связывает изображения и текст в общем пространстве?", ("clip",), "Это CLIP."), ("Как называется постепенное удаление шума при генерации изображения?", ("обратная диффузия", "denoising", "денойзинг"), "Диффузионная модель учится обращать процесс зашумления.")],
}

PRACTICUM_QUIZZES = {
    1: [
        ("Какая регуляризация способствует обнулению части весов: L1 или L2?", ("l1",), "L1 может давать разреженные веса и выполнять отбор признаков."),
        ("Как называется автоматический подбор гиперпараметров с эффективным поиском?", ("optuna",), "Optuna автоматизирует поиск гиперпараметров."),
        ("Какая библиотека объясняет предсказания через значения Шепли?", ("shap",), "SHAP используют для локальной и глобальной интерпретации."),
        ("Как называется система для логирования параметров, метрик и моделей?", ("mlflow",), "MLflow помогает сравнивать и воспроизводить эксперименты."),
        ("Как называется объединение предсказаний нескольких моделей метамоделью?", ("stacking", "стекинг", "стэкинг"), "В stacking метамодель учится на прогнозах базовых моделей."),
        ("Какая техника исправляет дисбаланс увеличением числа объектов редкого класса?", ("oversampling", "оверсэмплинг"), "Oversampling увеличивает представленность редкого класса."),
    ],
    2: STUDY_QUIZZES["applied"],
    3: [
        ("Какой инструмент версионирует данные и ML-артефакты поверх Git?", ("dvc",), "DVC хранит версии данных и связывает их с кодом."),
        ("Какой Python-фреймворк подходит для REST API модели?", ("fastapi", "fast api"), "FastAPI предоставляет типизацию и автоматическую документацию."),
        ("Как называется файл инструкций сборки Docker-образа?", ("dockerfile",), "Dockerfile описывает слои и команду запуска образа."),
        ("Какой HTTP-метод обычно получает ресурс без изменения состояния?", ("get",), "GET используют для чтения ресурса."),
        ("Как называется изолированная среда зависимостей Python?", ("виртуальное окружение", "venv", "virtual environment"), "Виртуальное окружение изолирует версии библиотек."),
        ("Как называется автоматическая проверка небольшого компонента программы?", ("юнит-тест", "unit test", "модульный тест"), "Unit test проверяет отдельную единицу поведения."),
    ],
    4: [
        ("Как называется разделение пользователей между контрольной и экспериментальной группами?", ("a/b-тест", "ab тест", "a/b тест"), "A/B-тест сравнивает варианты на случайных группах."),
        ("Как называется вероятность получить наблюдаемый результат при верной нулевой гипотезе?", ("p-value", "p value", "p-значение"), "Это p-value."),
        ("Как называется изменение распределения входных признаков со временем?", ("data drift", "дрейф данных"), "Data drift отслеживают после запуска модели."),
        ("Как называется обработка накопленной группы объектов по расписанию?", ("batch inference", "пакетный инференс", "batch"), "Batch inference не требует ответа в реальном времени."),
        ("Как называется выдача прогноза сразу на пользовательский запрос?", ("online inference", "онлайн инференс", "online"), "Online inference требует контролировать задержку."),
        ("Что нужно мониторить кроме технической ML-метрики?", ("бизнес-метрику", "бизнес метрику", "business metric"), "Качество модели должно быть связано с результатом продукта."),
    ],
    5: STUDY_QUIZZES["interview"],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS olympiads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                subject TEXT NOT NULL CHECK(subject IN ('Математика', 'Информатика')),
                event_date TEXT,
                goal TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                subject TEXT NOT NULL CHECK(subject IN ('Математика', 'Информатика')),
                color TEXT NOT NULL DEFAULT '#2563eb',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                olympiad_id INTEGER REFERENCES olympiads(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL CHECK(difficulty IN ('Легко', 'Средне', 'Сложно')),
                status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned', 'in_progress', 'solved')),
                due_date TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(user_id, completed_at);
            CREATE TABLE IF NOT EXISTS study_plan_progress (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                plan_date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, plan_date)
            );
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        for name, definition in (
            ("planned_minutes", "INTEGER NOT NULL DEFAULT 0"),
            ("spent_minutes", "INTEGER NOT NULL DEFAULT 0"),
            ("condition_text", "TEXT NOT NULL DEFAULT ''"),
            ("condition_image", "TEXT"),
            ("problem_count", "INTEGER NOT NULL DEFAULT 1"),
            ("solved_count", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in columns:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {name} {definition}")
        plan_columns = {row["name"] for row in conn.execute("PRAGMA table_info(study_plan_progress)")}
        if "drills_completed" not in plan_columns:
            conn.execute("ALTER TABLE study_plan_progress ADD COLUMN drills_completed INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE study_plan_progress SET drills_completed=7 WHERE completed=1")
        if "quiz_version" not in plan_columns:
            conn.execute("ALTER TABLE study_plan_progress ADD COLUMN quiz_version INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE tasks SET solved_count=1 WHERE status='solved' AND solved_count=0")
        for table in ("topics", "olympiads"):
            schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()["sql"]
            if "Искусственный интеллект" not in schema:
                migrate_subject_table(conn, table)


def migrate_subject_table(conn, table):
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    extra = "color TEXT NOT NULL DEFAULT '#2563eb'" if table == "topics" else "event_date TEXT, goal TEXT NOT NULL DEFAULT ''"
    conn.execute(f"""CREATE TABLE {table}_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        subject TEXT NOT NULL CHECK(subject IN ('Математика', 'Информатика', 'Искусственный интеллект')),
        {extra}, created_at TEXT NOT NULL)""")
    fields = "id,user_id,name,subject,color,created_at" if table == "topics" else "id,user_id,name,subject,event_date,goal,created_at"
    conn.execute(f"INSERT INTO {table}_new({fields}) SELECT {fields} FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password, stored):
    try:
        salt_hex, expected = stored.split(":", 1)
        actual = hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def row_dict(row):
    return dict(row) if row else None


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    server_version = "RYD/1.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def json_response(self, data, status=200, headers=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 5_000_000:
                raise ApiError(413, "Слишком большой запрос")
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            raise ApiError(400, "Некорректный JSON")

    def token(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie"))
        morsel = jar.get("ryd_session")
        return morsel.value if morsel else None

    def user(self, required=True):
        token = self.token()
        if token:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            with db() as conn:
                row = conn.execute(
                    """SELECT u.id, u.name, u.email, u.created_at FROM sessions s
                       JOIN users u ON u.id = s.user_id
                       WHERE s.token_hash = ? AND s.expires_at > ?""",
                    (token_hash, now()),
                ).fetchone()
                if row:
                    return row_dict(row)
        if required:
            raise ApiError(401, "Необходима авторизация")
        return None

    def route(self):
        return urlparse(self.path).path.rstrip("/") or "/"

    def do_GET(self):
        try:
            path = self.route()
            if path == "/api/me":
                return self.json_response({"user": self.user(False)})
            if path == "/api/dashboard":
                return self.dashboard()
            if path == "/api/olympiads":
                return self.list_items("olympiads")
            if path == "/api/topics":
                return self.list_items("topics")
            if path == "/api/notes":
                return self.list_notes()
            if path == "/api/tasks":
                return self.list_tasks()
            if path == "/api/stats":
                return self.stats()
            if path == "/api/study-plan":
                return self.study_plan()
            if path.startswith("/api/"):
                raise ApiError(404, "Маршрут не найден")
            return self.static(path)
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)
        except Exception as error:
            print("Unhandled error:", repr(error))
            self.json_response({"error": "Внутренняя ошибка сервера"}, 500)

    def do_POST(self):
        try:
            path = self.route()
            if path == "/api/auth/register":
                return self.register()
            if path == "/api/auth/login":
                return self.login()
            if path == "/api/auth/logout":
                return self.logout()
            if path == "/api/olympiads":
                return self.create_olympiad()
            if path == "/api/topics":
                return self.create_topic()
            if path == "/api/tasks":
                return self.create_task()
            if path == "/api/notes":
                return self.create_note()
            if path == "/api/study-plan/check":
                return self.check_plan_answer()
            raise ApiError(404, "Маршрут не найден")
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)
        except sqlite3.IntegrityError:
            self.json_response({"error": "Такая запись уже существует или данные некорректны"}, 409)
        except Exception as error:
            print("Unhandled error:", repr(error))
            self.json_response({"error": "Внутренняя ошибка сервера"}, 500)

    def do_PATCH(self):
        try:
            parts = self.route().split("/")
            if len(parts) == 4 and parts[1:3] == ["api", "tasks"]:
                return self.update_task(int(parts[3]))
            if len(parts) == 4 and parts[1:3] == ["api", "study-plan"]:
                return self.update_plan_day(parts[3])
            raise ApiError(404, "Маршрут не найден")
        except ValueError:
            self.json_response({"error": "Некорректный идентификатор"}, 400)
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)

    def do_DELETE(self):
        try:
            parts = self.route().split("/")
            if len(parts) == 4 and parts[1] == "api" and parts[2] in ("tasks", "topics", "olympiads", "notes"):
                return self.delete_item(parts[2], int(parts[3]))
            raise ApiError(404, "Маршрут не найден")
        except ValueError:
            self.json_response({"error": "Некорректный идентификатор"}, 400)
        except ApiError as error:
            self.json_response({"error": error.message}, error.status)

    def session_header(self, token, expires):
        secure = "; Secure" if os.environ.get("RYD_SECURE_COOKIE") == "1" else ""
        return {"Set-Cookie": f"ryd_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_DAYS * 86400}{secure}"}

    def register(self):
        data = self.body()
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        if len(name) < 2 or "@" not in email or len(password) < 8:
            raise ApiError(400, "Укажите имя, корректную почту и пароль от 8 символов")
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO users(name, email, password_hash, created_at) VALUES(?, ?, ?, ?)",
                (name[:80], email[:160], hash_password(password), now()),
            )
            user_id = cur.lastrowid
            self.seed_user(conn, user_id)
        return self.start_session(user_id, 201)

    def login(self):
        data = self.body()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        with db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise ApiError(401, "Неверная почта или пароль")
        return self.start_session(row["id"])

    def start_session(self, user_id, status=200):
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now(),))
            conn.execute(
                "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES(?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), user_id, expires.isoformat()),
            )
            user = row_dict(conn.execute("SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone())
        self.json_response({"user": user}, status, self.session_header(token, expires))

    def logout(self):
        token = self.token()
        if token:
            with db() as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
        self.json_response({"ok": True}, headers={"Set-Cookie": "ryd_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    def seed_user(self, conn, user_id):
        timestamp = now()
        topics = [("Комбинаторика", "Математика", "#2563eb"), ("Динамическое программирование", "Информатика", "#7c3aed"), ("Теория чисел", "Математика", "#0891b2")]
        ids = []
        for item in topics:
            ids.append(conn.execute("INSERT INTO topics(user_id, name, subject, color, created_at) VALUES(?, ?, ?, ?, ?)", (user_id, *item, timestamp)).lastrowid)
        olympiad_id = conn.execute("INSERT INTO olympiads(user_id, name, subject, event_date, goal, created_at) VALUES(?, ?, ?, ?, ?, ?)", (user_id, "Региональный этап ВсОШ", "Математика", None, "Уверенно решить 6 задач", timestamp)).lastrowid
        conn.execute("INSERT INTO tasks(user_id, topic_id, olympiad_id, title, description, difficulty, status, due_date, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", (user_id, ids[0], olympiad_id, "Разобрать принцип Дирихле", "Решить подборку из 5 задач.", "Средне", "in_progress", None, timestamp))
        conn.execute("INSERT INTO tasks(user_id, topic_id, title, description, difficulty, status, due_date, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)", (user_id, ids[1], "Задачи на рюкзак", "Повторить переходы и оптимизацию памяти.", "Сложно", "planned", None, timestamp))

    def list_items(self, table):
        user = self.user()
        order = "event_date IS NULL, event_date" if table == "olympiads" else "created_at DESC"
        with db() as conn:
            rows = [row_dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE user_id = ? ORDER BY {order}", (user["id"],))]
        self.json_response({table: rows})

    def list_tasks(self):
        user = self.user()
        with db() as conn:
            rows = [row_dict(row) for row in conn.execute(
                """SELECT t.*, p.name topic_name, p.subject, p.color, o.name olympiad_name
                   FROM tasks t LEFT JOIN topics p ON p.id=t.topic_id LEFT JOIN olympiads o ON o.id=t.olympiad_id
                   WHERE t.user_id=? ORDER BY CASE t.status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END, t.created_at DESC""", (user["id"],))]
        self.json_response({"tasks": rows})

    def list_notes(self):
        user = self.user()
        with db() as conn:
            rows = [row_dict(row) for row in conn.execute(
                "SELECT n.*, p.name topic_name FROM notes n JOIN topics p ON p.id=n.topic_id WHERE n.user_id=? ORDER BY n.created_at DESC",
                (user["id"],),
            )]
        self.json_response({"notes": rows})

    def create_olympiad(self):
        user, data = self.user(), self.body()
        name, subject = str(data.get("name", "")).strip(), data.get("subject")
        if not name or subject not in ("Математика", "Информатика", "Искусственный интеллект"):
            raise ApiError(400, "Заполните название и предмет")
        with db() as conn:
            cur = conn.execute("INSERT INTO olympiads(user_id,name,subject,event_date,goal,created_at) VALUES(?,?,?,?,?,?)", (user["id"], name[:160], subject, data.get("event_date") or None, str(data.get("goal", ""))[:300], now()))
            item = row_dict(conn.execute("SELECT * FROM olympiads WHERE id=?", (cur.lastrowid,)).fetchone())
        self.json_response({"olympiad": item}, 201)

    def create_topic(self):
        user, data = self.user(), self.body()
        name, subject = str(data.get("name", "")).strip(), data.get("subject")
        if not name or subject not in ("Математика", "Информатика", "Искусственный интеллект"):
            raise ApiError(400, "Заполните название и предмет")
        color = data.get("color") if str(data.get("color", "")).startswith("#") else "#2563eb"
        with db() as conn:
            cur = conn.execute("INSERT INTO topics(user_id,name,subject,color,created_at) VALUES(?,?,?,?,?)", (user["id"], name[:120], subject, color[:7], now()))
            item = row_dict(conn.execute("SELECT * FROM topics WHERE id=?", (cur.lastrowid,)).fetchone())
        self.json_response({"topic": item}, 201)

    def create_note(self):
        user, data = self.user(), self.body()
        title, content = str(data.get("title", "")).strip(), str(data.get("content", "")).strip()
        try:
            topic_id = int(data.get("topic_id"))
        except (TypeError, ValueError):
            raise ApiError(400, "Выберите тему")
        if not title or not content:
            raise ApiError(400, "Заполните название и текст конспекта")
        with db() as conn:
            if not conn.execute("SELECT 1 FROM topics WHERE id=? AND user_id=?", (topic_id, user["id"])).fetchone():
                raise ApiError(400, "Выбрана недоступная тема")
            cur = conn.execute("INSERT INTO notes(user_id,topic_id,title,content,created_at) VALUES(?,?,?,?,?)", (user["id"], topic_id, title[:160], content[:20000], now()))
        self.json_response({"id": cur.lastrowid}, 201)

    def create_task(self):
        user, data = self.user(), self.body()
        title, difficulty = str(data.get("title", "")).strip(), data.get("difficulty", "Средне")
        if not title or difficulty not in ("Легко", "Средне", "Сложно"):
            raise ApiError(400, "Заполните название и сложность")
        topic_id = int(data["topic_id"]) if data.get("topic_id") else None
        olympiad_id = int(data["olympiad_id"]) if data.get("olympiad_id") else None
        try:
            planned_minutes = max(0, min(int(data.get("planned_minutes") or 0), 100000))
            problem_count = max(1, min(int(data.get("problem_count") or 1), 10000))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректное время или количество задач")
        image = data.get("condition_image") or None
        if image and (not isinstance(image, str) or not image.startswith("data:image/jpeg;base64,") or len(image) > 4_500_000):
            raise ApiError(400, "Фото должно быть в формате JPEG и не больше 3 МБ")
        with db() as conn:
            for table, item_id in (("topics", topic_id), ("olympiads", olympiad_id)):
                if item_id and not conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND user_id=?", (item_id, user["id"])).fetchone():
                    raise ApiError(400, "Выбрана недоступная связь")
            cur = conn.execute("""INSERT INTO tasks(user_id,topic_id,olympiad_id,title,description,difficulty,status,due_date,created_at,planned_minutes,condition_text,condition_image,problem_count)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (user["id"], topic_id, olympiad_id, title[:200], str(data.get("description", ""))[:2000], difficulty, "planned", data.get("due_date") or None, now(), planned_minutes, str(data.get("condition_text", ""))[:10000], image, problem_count))
        self.json_response({"id": cur.lastrowid}, 201)

    def update_task(self, item_id):
        user, data = self.user(), self.body()
        if "status" not in data:
            return self.edit_task(user, item_id, data)
        allowed = {"planned", "in_progress", "solved"}
        status = data.get("status")
        if status not in allowed:
            raise ApiError(400, "Некорректный статус")
        try:
            spent = max(0, min(int(data.get("spent_minutes") or 0), 100000))
            solved_count = max(0, int(data.get("solved_count") or 0))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректное время или количество решенных задач")
        if status == "solved" and spent <= 0:
            raise ApiError(400, "Укажите время, потраченное на задачу")
        completed = now() if status == "solved" else None
        with db() as conn:
            task = conn.execute("SELECT problem_count FROM tasks WHERE id=? AND user_id=?", (item_id, user["id"])).fetchone()
            if not task:
                raise ApiError(404, "Задача не найдена")
            if solved_count > task["problem_count"]:
                raise ApiError(400, "Решенных задач не может быть больше общего количества")
            cur = conn.execute("UPDATE tasks SET status=?, completed_at=?, spent_minutes=?, solved_count=? WHERE id=? AND user_id=?", (status, completed, spent, solved_count, item_id, user["id"]))
        if not cur.rowcount:
            raise ApiError(404, "Задача не найдена")
        self.json_response({"ok": True})

    def edit_task(self, user, item_id, data):
        title, difficulty = str(data.get("title", "")).strip(), data.get("difficulty")
        if not title or difficulty not in ("Легко", "Средне", "Сложно"):
            raise ApiError(400, "Заполните название и сложность")
        try:
            topic_id = int(data["topic_id"]) if data.get("topic_id") else None
            olympiad_id = int(data["olympiad_id"]) if data.get("olympiad_id") else None
            planned_minutes = max(0, min(int(data.get("planned_minutes") or 0), 100000))
            problem_count = max(1, min(int(data.get("problem_count") or 1), 10000))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректные связи, время или количество задач")
        image = data.get("condition_image")
        if image and (not isinstance(image, str) or not image.startswith("data:image/jpeg;base64,") or len(image) > 4_500_000):
            raise ApiError(400, "Фото должно быть в формате JPEG и не больше 3 МБ")
        with db() as conn:
            current = conn.execute("SELECT solved_count, condition_image FROM tasks WHERE id=? AND user_id=?", (item_id, user["id"])).fetchone()
            if not current:
                raise ApiError(404, "Задача не найдена")
            if current["solved_count"] > problem_count:
                raise ApiError(400, "Общее количество не может быть меньше уже решенных задач")
            for table, linked_id in (("topics", topic_id), ("olympiads", olympiad_id)):
                if linked_id and not conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND user_id=?", (linked_id, user["id"])).fetchone():
                    raise ApiError(400, "Выбрана недоступная связь")
            if "condition_image" not in data:
                image = current["condition_image"]
            conn.execute("""UPDATE tasks SET topic_id=?, olympiad_id=?, title=?, description=?, difficulty=?, due_date=?,
                planned_minutes=?, problem_count=?, condition_text=?, condition_image=? WHERE id=? AND user_id=?""",
                (topic_id, olympiad_id, title[:200], str(data.get("description", ""))[:2000], difficulty,
                 data.get("due_date") or None, planned_minutes, problem_count, str(data.get("condition_text", ""))[:10000],
                 image, item_id, user["id"]))
        self.json_response({"ok": True})

    def delete_item(self, table, item_id):
        user = self.user()
        with db() as conn:
            cur = conn.execute(f"DELETE FROM {table} WHERE id=? AND user_id=?", (item_id, user["id"]))
        if not cur.rowcount:
            raise ApiError(404, "Запись не найдена")
        self.json_response({"ok": True})

    def dashboard(self):
        user = self.user()
        with db() as conn:
            counts = row_dict(conn.execute("""SELECT COUNT(*) total, SUM(status='solved') solved, SUM(status='in_progress') active,
                SUM(completed_at >= datetime('now','-30 days')) month_solved, SUM(spent_minutes) spent_minutes, SUM(solved_count) solved_problems FROM tasks WHERE user_id=?""", (user["id"],)).fetchone())
            upcoming = [row_dict(r) for r in conn.execute("SELECT * FROM olympiads WHERE user_id=? AND event_date>=date('now') ORDER BY event_date LIMIT 3", (user["id"],))]
            recent = [row_dict(r) for r in conn.execute("""SELECT t.*, p.name topic_name, p.color, p.subject FROM tasks t LEFT JOIN topics p ON p.id=t.topic_id
                WHERE t.user_id=? ORDER BY CASE t.status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END, t.created_at DESC LIMIT 5""", (user["id"],))]
        counts = {key: (value or 0) for key, value in counts.items()}
        self.json_response({"counts": counts, "upcoming": upcoming, "tasks": recent})

    def stats(self):
        user = self.user()
        with db() as conn:
            days = {r["day"]: r["count"] for r in conn.execute("""SELECT date(completed_at) day, COUNT(*) count FROM tasks
                WHERE user_id=? AND completed_at >= datetime('now','-29 days') GROUP BY date(completed_at)""", (user["id"],))}
            subjects = [row_dict(r) for r in conn.execute("""SELECT p.subject, COUNT(t.id) total, SUM(t.status='solved') solved FROM topics p
                LEFT JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? GROUP BY p.subject""", (user["id"],))]
            topics = [row_dict(r) for r in conn.execute("""SELECT p.name, p.color, COUNT(t.id) total, SUM(t.status='solved') solved, SUM(t.spent_minutes) spent_minutes FROM topics p
                LEFT JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? GROUP BY p.id ORDER BY solved DESC, total DESC LIMIT 6""", (user["id"],))]
            month_topics = [row_dict(r) for r in conn.execute("""SELECT p.name, p.color, SUM(t.spent_minutes) spent_minutes, SUM(t.solved_count) solved_count FROM topics p
                JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? AND t.completed_at >= datetime('now','-29 days')
                GROUP BY p.id HAVING spent_minutes > 0 ORDER BY spent_minutes DESC""", (user["id"],))]
            day_topics = [row_dict(r) for r in conn.execute("""SELECT p.name, p.color, SUM(t.spent_minutes) spent_minutes, SUM(t.solved_count) solved_count FROM topics p
                JOIN tasks t ON t.topic_id=p.id WHERE p.user_id=? AND date(t.completed_at)=date('now')
                GROUP BY p.id HAVING spent_minutes > 0 ORDER BY spent_minutes DESC""", (user["id"],))]
        series = []
        today = datetime.now(timezone.utc).date()
        for offset in range(29, -1, -1):
            day = today - timedelta(days=offset)
            series.append({"date": day.isoformat(), "count": days.get(day.isoformat(), 0)})
        month_minutes = sum(item["spent_minutes"] or 0 for item in month_topics)
        day_minutes = sum(item["spent_minutes"] or 0 for item in day_topics)
        month_solved = sum(item["solved_count"] or 0 for item in month_topics)
        day_solved = sum(item["solved_count"] or 0 for item in day_topics)
        with db() as conn:
            lifetime = row_dict(conn.execute("SELECT SUM(spent_minutes) spent_minutes, SUM(solved_count) solved_count FROM tasks WHERE user_id=?", (user["id"],)).fetchone())
        self.json_response({"series": series, "subjects": subjects, "topics": topics,
                            "month_topics": month_topics, "day_topics": day_topics,
                            "month_minutes": month_minutes, "day_minutes": day_minutes,
                            "month_solved": month_solved, "day_solved": day_solved,
                            "lifetime_minutes": lifetime["spent_minutes"] or 0,
                            "lifetime_solved": lifetime["solved_count"] or 0})

    def study_plan_item(self, day):
        weekday = day.weekday()
        if day <= date_type(2026, 7, 31):
            phase = "Темы 9–10 · математика и фундамент"
            tasks = [
                "Повторить линейную алгебру: матричное умножение, ранг и собственные векторы",
                "Практика: реализовать k-means или градиентный спуск через NumPy",
                "Закрыть текущий семинар и самостоятельно решить домашнюю работу",
                "Решить 5 коротких задач по линейной алгебре",
                "Алгоритмы: массивы, строки, словари и оценка сложности",
                "Мини-проект: масштабирование, PCA и k-means на небольшом датасете",
                "Недельный тест по темам 3–10 и разбор ошибок",
            ]
            drills = [
                ("Вычисли произведение двух матриц 2x2, найди ранг результата и проверь ответ в NumPy.", "Объясни, что означают линейная зависимость, ранг и собственный вектор.", "Можешь без конспекта связать собственные векторы с направлением главных компонент."),
                ("Реализуй один шаг k-means: расстояния, назначение кластеров и пересчет центров.", "Объясни, почему масштаб признаков и инициализация меняют результат k-means.", "Код не использует sklearn и совпадает с ним на простом наборе точек."),
                ("Повтори одно решение домашней работы с нуля и выпиши два места, где ошибся раньше.", "Расскажи решение самой сложной задачи так, будто отвечаешь преподавателю.", "Каждый переход обоснован, а не восстановлен по памяти из разбора."),
                ("Реши 5 задач: матричное умножение, транспонирование, ранг, базис и линейная зависимость.", "Объясни геометрический смысл скалярного произведения и нормы.", "Не менее 4 из 5 ответов верны без подсказок."),
                ("Реши две задачи на массивы или словари с ограничением 30 минут на каждую.", "Для каждого решения назови временную и пространственную сложность.", "Оба решения проходят граничные случаи: пустой ввод, один элемент и повторы."),
                ("Сделай scaling, PCA и k-means на одном датасете и построй график кластеров.", "Объясни, почему визуально красивые кластеры не обязательно полезны.", "Есть метрика качества, baseline и письменный вывод об ограничениях."),
                ("Ответь письменно на 10 вопросов по темам 3–10 без конспекта.", "За 5 минут объясни PCA, k-means и градиентный спуск.", "Минимум 8 из 10 ответов верны; ошибки добавлены в список повторения."),
            ]
        elif day <= date_type(2026, 8, 31):
            phase = "Темы 11–15 · EDA, метрики и валидация"
            tasks = [
                "Семинар текущего модуля и конспект на 1–2 страницы",
                "Домашняя работа без подсказок, затем выписать ошибки",
                "Практика EDA: пропуски, выбросы, распределения и корреляции",
                "Алгоритмы: 2 задачи без подсказок",
                "SQL: SELECT, WHERE, GROUP BY и JOIN",
                "Сравнить метрики на несбалансированных данных",
                "Повтор недели: leakage, train/validation/test и cross-validation",
            ]
            drills = [
                ("Сожми текущий семинар до пяти тезисов и одного примера на каждый тезис.", "Ответь на 5 вопросов по семинару без конспекта.", "Можешь назвать предположения метода, ограничения и подходящую метрику."),
                ("Перерешай одну задачу домашней работы другим способом.", "Объясни причину каждой ошибки из первой попытки.", "Повторное решение получено без просмотра разбора."),
                ("На незнакомом датасете найди пропуски, выбросы и подозрительные корреляции.", "Назови три источника утечки данных при EDA.", "Каждое наблюдение подтверждено таблицей или графиком, а не впечатлением."),
                ("Реши две задачи на строки, сортировки или хеш-таблицы за 60 минут.", "Докажи корректность ключевого шага одного решения.", "Решения проходят собственные граничные тесты."),
                ("Напиши запрос с JOIN, GROUP BY и HAVING на двух связанных таблицах.", "Объясни разницу WHERE и HAVING, INNER и LEFT JOIN.", "Результат проверен вручную на маленьком наборе данных."),
                ("Посчитай precision, recall, F1, ROC-AUC и PR-AUC для несбалансированного примера.", "Объясни, какую метрику выберешь при дорогом false negative.", "Выбор метрики связан с ценой ошибок и бизнес-задачей."),
                ("Для трех кейсов выбери split: stratified, group или time-series.", "Объясни, почему тест нельзя использовать для подбора гиперпараметров.", "Во всех кейсах указаны возможная утечка и честная схема валидации."),
            ]
        elif day <= date_type(2026, 10, 31):
            phase = "Темы 16–23 · алгоритмы, модели и нейросети"
            tasks = [
                "Семинар курса и карточки с ключевыми определениями",
                "Домашняя работа: сначала собственное решение, потом разбор",
                "Решить 2 алгоритмические задачи и оценить сложность",
                "SQL: CTE, подзапросы или оконные функции",
                "Практика ML: baseline, Pipeline и таблица экспериментов",
                "PyTorch: написать или улучшить training loop",
                "Повторить неделю и объяснить одну тему вслух за 5 минут",
            ]
            drills = [
                ("Составь 7 карточек по текущей теме: термин на одной стороне, смысл и пример на другой.", "Объясни тему без формул, затем добавь формальное определение.", "На все карточки отвечаешь без паузы дольше 20 секунд."),
                ("Воспроизведи ключевой алгоритм домашней работы на чистом листе.", "Назови альтернативный подход и сравни сложности.", "Решение проходит примеры и два собственных граничных теста."),
                ("Реши две задачи текущего алгоритмического блока с таймером.", "Обоснуй корректность и сложность лучшего решения.", "Нет скрытой квадратичной операции внутри цикла."),
                ("Реши SQL-задачу с CTE и оконной функцией.", "Объясни порядок выполнения частей SQL-запроса.", "Запрос корректно обрабатывает NULL и повторяющиеся строки."),
                ("Сравни baseline и настроенную модель в одном Pipeline.", "Объясни, какие параметры нельзя подбирать на test.", "Эксперимент воспроизводим: seed, split, метрика и параметры записаны."),
                ("Напиши forward, loss, backward и optimizer step без копирования.", "Объясни chain rule и назначение zero_grad.", "Loss уменьшается, shapes проверены, модель умеет перейти в eval mode."),
                ("Выбери слабую тему недели и ответь на 10 быстрых вопросов.", "Проведи пятиминутный рассказ с примером и ограничениями.", "Минимум 8 ответов верны без конспекта."),
            ]
        elif day <= date_type(2026, 12, 31):
            phase = "Темы 24–29 · NLP, attention и трансформеры"
            tasks = [
                "Семинар: токенизация, embeddings или self-attention",
                "Домашняя работа и повторная реализация через 2–3 дня",
                "Собрать TF-IDF baseline для текстовой классификации",
                "Решить 2 задачи по графам, динамике или оптимизации",
                "SQL-сессия: 3 задачи с агрегациями и JOIN",
                "Практика: сравнить baseline с нейросетевой моделью",
                "Устно объяснить Transformer, BERT и маски без конспекта",
            ]
            drills = [
                ("Токенизируй три предложения и проверь input_ids, padding и attention_mask.", "Объясни разницу токена, эмбеддинга и позиционного кодирования.", "Можешь предсказать shapes тензоров на каждом шаге."),
                ("Повтори ключевую реализацию модуля без просмотра исходного решения.", "Объясни, где в решении возможна утечка или переобучение.", "Результат воспроизводится на той же валидации."),
                ("Обучи TF-IDF + LogisticRegression и сохрани метрики как baseline.", "Объясни, почему такой baseline обязателен перед нейросетью.", "Есть F1, confusion matrix и пять разобранных ошибок."),
                ("Реши две задачи на графы, динамику или оптимизацию с оценкой сложности.", "Докажи корректность перехода или алгоритма обхода.", "Решения проходят граничные и случайные маленькие тесты."),
                ("Напиши SQL-запрос с двумя JOIN и агрегацией.", "Объясни, как JOIN может случайно размножить строки.", "Проверены количество строк до и после соединения."),
                ("Сравни baseline и нейросеть на одном split и одной метрике.", "Объясни три причины, почему сложная модель может проиграть baseline.", "Вывод опирается на метрики и анализ ошибок."),
                ("Нарисуй self-attention и подпиши Q, K, V, softmax и mask.", "Сравни encoder, decoder и BERT без конспекта.", "Можешь объяснить назначение каждого блока и размеры матриц."),
            ]
        elif day <= date_type(2027, 2, 28):
            phase = "Закрепление · классический ML, SQL и LLM"
            tasks = [
                "Повторить классический ML и ответить на 10 вопросов собеседования",
                "Решить 3 алгоритмические задачи",
                "SQL: оконные функции, даты и CASE WHEN",
                "Разобрать leakage, bias-variance и выбор метрики",
                "RAG: проверить retrieval на контрольном наборе вопросов",
                "Работа над главным проектом: эксперимент или анализ ошибок",
                "Недельный mock interview и список пробелов",
            ]
            drills = [
                ("Ответь на 10 случайных вопросов по классическому ML с таймером 90 секунд.", "Сравни линейную модель, дерево и boosting для одного кейса.", "В каждом ответе есть предположения, метрика и риск ошибки."),
                ("Реши три алгоритмические задачи: easy, medium и повтор слабой темы.", "Объясни решение medium до написания кода.", "Все задачи проходят тесты в пределах заявленной сложности."),
                ("Реши три SQL-задачи на окна, даты и CASE WHEN.", "Объясни PARTITION BY и отличие ROW_NUMBER от RANK.", "Запросы проверены на NULL, ties и границах дат."),
                ("Найди leakage в трех описаниях ML-пайплайна.", "Объясни bias-variance trade-off на примере.", "Для каждого кейса предложена честная валидация и метрика."),
                ("Сравни два chunking-подхода по Recall@k на контрольных вопросах.", "Объясни разницу retrieval, reranking и generation.", "Есть численная метрика и разбор минимум трех провалов."),
                ("Проведи один воспроизводимый эксперимент главного проекта.", "За 3 минуты расскажи baseline, split, метрику и результат.", "Эксперимент запускается по README и записан в таблицу."),
                ("Запиши mock interview и выпиши пять слабых ответов.", "Повтори слабые ответы без слов-паразитов и ухода от вопроса.", "Каждый новый ответ короче двух минут и содержит конкретный пример."),
            ]
        elif day <= date_type(2027, 4, 30):
            phase = "Собеседования · проект, ML-case и резюме"
            tasks = [
                "ML-интервью: метрики, валидация и вопросы по проекту",
                "Алгоритмическая задача с таймером 35 минут",
                "SQL-сессия из 3 задач",
                "ML-case: постановка задачи, baseline и бизнес-метрика",
                "Обновить README и воспроизводимый запуск проекта",
                "Mock interview: рассказ о себе и главном проекте",
                "Разобрать ошибки недели и повторить слабые темы",
            ]
            drills = [
                ("Пройди 15 вопросов по ML с ограничением 90 секунд на ответ.", "Объясни метрику, split и leakage своего проекта.", "Не менее 12 ответов полные и без подсказок."),
                ("Реши одну medium-задачу за 35 минут в чистом редакторе.", "Сначала проговори идею, доказательство и сложность.", "Код проходит примеры и собственные edge cases."),
                ("Реши три SQL-задачи подряд без документации.", "Объясни результат каждой промежуточной таблицы.", "Все запросы корректны для NULL и дубликатов."),
                ("Разбери ML-case от бизнес-цели до мониторинга модели.", "Защити выбор baseline, split и offline-метрики.", "Указаны ограничения, цена ошибок и план эксперимента."),
                ("Запусти проект строго по README в чистом окружении.", "Расскажи, что не сработало и почему.", "Команда запуска воспроизводима, секретов и абсолютных путей нет."),
                ("Проведи 45-минутное mock interview с записью.", "Ответь на уточняющие вопросы по проекту без презентации.", "После разбора сформулированы три конкретных улучшения."),
                ("Перерешай три ошибки недели без просмотра ответов.", "Объясни правильные решения простыми словами.", "Повторные ответы верны и занесены в карточки."),
            ]
        else:
            phase = "Финальная подготовка · симуляции отбора"
            tasks = [
                "Повторить классический ML и статистику",
                "Алгоритмическая задача в формате отбора",
                "SQL-сессия и проверка типичных ошибок",
                "PyTorch или NLP: 30 минут вопросов и практики",
                "Провести полный ML-case",
                "Повторить карточки по главному проекту",
                "Легкое повторение, сон и план следующей недели",
            ]
            drills = [
                ("Реши смешанный тест из 15 вопросов по ML и статистике.", "Объясни три самых слабых ответа повторно.", "Не менее 12 правильных ответов без конспекта."),
                ("Реши алгоритмическую задачу в полном формате отбора.", "Проговори решение до кода и оцени сложность.", "Уложился во время, код проходит edge cases."),
                ("Реши SQL-секцию с таймером и без документации.", "Объясни JOIN, окна и агрегации из решения.", "Нет ошибок на NULL, дубликатах и границах дат."),
                ("Воспроизведи training loop или NLP pipeline с нуля.", "Объясни shapes, loss, режимы train и eval.", "Код запускается, результат воспроизводим."),
                ("Проведи ML-case от постановки задачи до мониторинга.", "Защити метрики и схему валидации перед воображаемым интервьюером.", "Ответ учитывает бизнес-цену ошибок и data drift."),
                ("Расскажи о проекте за 5 минут, затем за 90 секунд.", "Ответь на пять неудобных вопросов об ограничениях.", "Рассказ конкретен: данные, baseline, эксперимент, результат."),
                ("Повтори только три слабые темы, не открывая новых.", "Кратко объясни каждую тему перед сном.", "Подготовка завершена вовремя, сохранен нормальный режим сна."),
            ]
        exact_titles = {
            date_type(2026, 7, 13): "K-means: алгоритм, масштабирование и реализация через NumPy",
            date_type(2026, 7, 14): "PCA: центрирование, ковариация и собственная реализация",
            date_type(2026, 7, 15): "Завершить домашнюю работу и разбор модуля 9",
            date_type(2026, 7, 16): "Дополнительно: закрыть пробелы модуля 8 по линейной алгебре",
            date_type(2026, 7, 17): "Алгоритмы: массивы, строки, словари и сложность",
            date_type(2026, 7, 18): "Мини-проект: scaling, PCA и k-means на датасете",
            date_type(2026, 7, 19): "Контрольный тест по модулям 3–9 и работа над ошибками",
            date_type(2026, 7, 20): "Функции, производные и геометрический смысл градиента",
            date_type(2026, 7, 21): "Выпуклые функции и условия минимума",
            date_type(2026, 7, 22): "Градиентный спуск и влияние learning rate",
            date_type(2026, 7, 23): "Неравенства, норма вектора и скалярное произведение",
            date_type(2026, 7, 24): "Алгоритмические задачи и первые SQL-запросы",
            date_type(2026, 7, 25): "Домашняя работа модуля 10 и численная проверка градиентов",
            date_type(2026, 7, 26): "Устный контроль по оптимизации и повтор слабых мест",
        }
        module = self.course_module(day)
        if module:
            lesson = ("Семинар", "Домашняя работа", "Разбор и работа над ошибками")[module[2] - 1]
            phase = f"Модуль {module[0]}. {module[1]} · день {module[2]} из 3"
            title = exact_titles.get(day, f"{lesson}: модуль {module[0]}")
        else:
            phase = "Дополнительная подготовка по программе"
            title = exact_titles.get(day, tasks[weekday])
        quiz_bank = self.quiz_bank(day)
        quiz_start = day.toordinal() % len(quiz_bank)
        quiz_items = [quiz_bank[(quiz_start + offset) % len(quiz_bank)] for offset in range(3)]
        drill_names = ("Быстрый вопрос", "Проверка понимания", "Контрольный вопрос")
        return {"date": day.isoformat(), "phase": phase, "title": title, "weekday": weekday,
                "drills": [{"id": index, "name": drill_names[index], "text": item[0]}
                           for index, item in enumerate(quiz_items)]}

    def study_quiz_key(self, day):
        if day <= date_type(2026, 8, 31):
            return "validation"
        if day <= date_type(2026, 10, 31):
            return "models"
        if day <= date_type(2026, 12, 31):
            return "nlp"
        if day <= date_type(2027, 2, 28):
            return "applied"
        return "interview"

    def course_module(self, day):
        modules = [
            (date_type(2026, 7, 13), 9, "ML. Кластеризация и методы понижения размерности"),
            (date_type(2026, 7, 20), 10, "Математика. Функции, неравенства и оптимизация"),
            (date_type(2026, 8, 3), 11, "ML. Exploratory Data Analysis"),
            (date_type(2026, 8, 10), 12, "Программирование. Введение в олимпиадное программирование"),
            (date_type(2026, 8, 17), 13, "ML. Метрики"),
            (date_type(2026, 8, 24), 14, "Математика. Дополнительные инструменты математики"),
            (date_type(2026, 8, 29), 15, "ML. Валидация"),
            (date_type(2026, 9, 1), 16, "Программирование. Бинарный поиск"),
            (date_type(2026, 9, 8), 17, "ML. Модели"),
            (date_type(2026, 9, 15), 18, "Программирование. Введение в динамическое программирование"),
            (date_type(2026, 9, 22), 19, "ML. Полносвязные нейросети"),
            (date_type(2026, 10, 1), 20, "Программирование. Графы"),
            (date_type(2026, 10, 8), 21, "ML. Сверточные нейросети"),
            (date_type(2026, 10, 15), 22, "Программирование. Кратчайшие пути и продолжение динамики"),
            (date_type(2026, 10, 22), 23, "ML. Автоэнкодеры"),
            (date_type(2026, 11, 2), 24, "Программирование. Тернарный поиск и переборы"),
            (date_type(2026, 11, 9), 25, "ML. Работа с текстами"),
            (date_type(2026, 11, 16), 26, "Программирование. Методы оптимизации"),
            (date_type(2026, 11, 23), 27, "ML. Языковое моделирование и механизм внимания"),
            (date_type(2026, 12, 1), 28, "ML. Трансформеры для текстов"),
            (date_type(2026, 12, 8), 29, "ML. Мультимодальные трансформеры и диффузии"),
        ]
        for start, number, title in modules:
            if start <= day <= start + timedelta(days=2):
                return number, title, (day - start).days + 1
        return None

    def quiz_bank(self, day):
        module = self.course_module(day)
        if module:
            if module[0] == 9:
                return STUDY_QUIZZES["module9"]
            if module[0] == 10:
                return STUDY_QUIZZES["module10"]
            return COURSE_MODULE_QUIZZES[module[0]]
        july_extra = {
            16: STUDY_QUIZZES["foundation"],
            17: STUDY_QUIZZES["models"],
            18: STUDY_QUIZZES["module9"],
            19: STUDY_QUIZZES["module9"],
            23: STUDY_QUIZZES["module10"],
            24: STUDY_QUIZZES["models"],
            25: STUDY_QUIZZES["module10"],
            26: STUDY_QUIZZES["module10"],
            27: STUDY_QUIZZES["module10"],
            28: STUDY_QUIZZES["module10"],
            29: STUDY_QUIZZES["module10"],
            30: STUDY_QUIZZES["module10"],
            31: STUDY_QUIZZES["module10"],
        }
        if day.year == 2026 and day.month == 7 and day.day in july_extra:
            return july_extra[day.day]
        if day.year == 2027 and day.month in PRACTICUM_QUIZZES:
            return PRACTICUM_QUIZZES[day.month]
        return STUDY_QUIZZES[self.study_quiz_key(day)]

    def study_day_details(self, day):
        month_plans = {
            (2026, 7): ("Темы 9–10", ["Кластеризация и k-means", "PCA и линейная алгебра", "Функции и производные", "Оптимизация и градиентный спуск"]),
            (2026, 8): ("Темы 11–15", ["EDA: пропуски и выбросы", "Олимпиадное программирование", "Метрики классификации и регрессии", "Валидация и утечки данных"]),
            (2026, 9): ("Темы 16–19", ["Бинарный поиск", "Feature engineering и гиперпараметры", "Динамическое программирование", "Полносвязные сети и PyTorch"]),
            (2026, 10): ("Темы 20–23", ["Графы", "CNN и transfer learning", "Кратчайшие пути", "Автоэнкодеры"]),
            (2026, 11): ("Темы 24–27", ["Переборы и оптимизация", "Тексты, BoW и TF-IDF", "Токенизация и эмбеддинги", "RNN и attention"]),
            (2026, 12): ("Темы 28–29", ["Self-attention и Transformer", "BERT и fine-tuning", "Encoder и decoder", "ViT, CLIP и мультимодальность"]),
            (2027, 1): ("Закрепление ML · программа Яндекс Практикума", ["Бизнес-задача, preprocessing и feature engineering", "Регуляризация L1/L2, SVM и многоклассовая классификация", "Optuna, дисбаланс классов, feature importance и SHAP", "Ансамбли, stacking и трекинг экспериментов в MLflow"]),
            (2027, 2): ("NLP и RAG · программа Яндекс Практикума", ["Классический NLP: BoW, TF-IDF, Word2Vec и FastText", "Transformer: генерация, суммаризация и инференс", "RAG: chunking, vector search, retrieval и дедупликация", "Оценка RAG, reranking, LoRA и ограничения мультимодальных моделей"]),
            (2027, 3): ("Главный проект · инженерный контур", ["Git, ООП и структура Python-приложения", "Pipeline, версионирование данных и экспериментов с DVC/MLflow", "REST API модели на FastAPI и автоматические тесты", "Docker, воспроизводимый запуск и документация проекта"]),
            (2027, 4): ("Собеседования и эксплуатация ML", ["A/B-тесты: гипотеза, метрики и статистическая значимость", "Мониторинг качества, data drift и продуктовые метрики", "ML system design: batch/online inference и отказоустойчивость", "Резюме, рассказ о проекте и полное mock interview"]),
            (2027, 5): ("Симуляция отбора", ["Повтор ML, SQL и алгоритмов", "Полная симуляция: ML-case, код и SQL", "Разбор слабых мест и вопросы по production ML", "Финальное легкое повторение без новых технологий"]),
            (2027, 6): ("День отбора", ["Короткое повторение и спокойный режим"]),
        }
        stage, topics = month_plans[(day.year, day.month)]
        module = self.course_module(day)
        if module:
            stage = f"Модуль {module[0]} курса · день {module[2]} из 3"
            topic = f"{module[0]}. {module[1]}"
        else:
            stage = "Дополнительная подготовка"
            topic = topics[min((day.day - 1) // 7, len(topics) - 1)]
            if day in {
                date_type(2026, 7, 16), date_type(2026, 7, 17), date_type(2026, 7, 18), date_type(2026, 7, 19),
                date_type(2026, 7, 23), date_type(2026, 7, 24), date_type(2026, 7, 25), date_type(2026, 7, 26),
            }:
                topic = {
                    16: "Повтор модуля 8. Линейная алгебра", 17: "Алгоритмы: массивы, строки и словари",
                    18: "Мини-проект по модулю 9", 19: "Контроль модулей 3–9",
                    23: "Закрепление математики модуля 10", 24: "Алгоритмы и начало SQL",
                    25: "Практика оптимизации", 26: "Контроль модуля 10",
                }[day.day]
        course_period = day <= date_type(2026, 12, 31)
        weekday = day.weekday()
        if course_period:
            schedules = [
                [(75, "Курс: семинар", f"Открой модуль «{topic}». Посмотри семинар активно: ставь паузу перед выводами и повторяй код."), (25, "Конспект", "Сожми материал до одной страницы: идея, формулы, предположения, ограничения и пример."), (20, "Проверка", "Ответь на вопросы тренажера на этой странице без конспекта.")],
                [(90, "Домашняя работа", f"Решай задания модуля «{topic}» самостоятельно. Разбор пока не открывай."), (20, "Диагностика", "Отметь места, где застрял, и сформулируй конкретный вопрос к каждому."), (10, "Тренажер", "Пройди три вопроса ниже и повтори неверные ответы.")],
                [(55, "Завершение домашней работы", "Доведи собственное решение до запуска или полного письменного ответа."), (30, "Разбор курса", "Сравни с официальным разбором и выпиши причины различий, а не только правильный код."), (25, "Повторная реализация", "Воспроизведи ключевую часть решения в чистом файле без копирования."), (10, "Тренажер", "Закрой проверку знаний на этой странице.")],
                [(20, "Разминка", "Повтори одну ранее решенную задачу без просмотра решения."), (75, "Алгоритмы", "Реши две задачи текущего алгоритмического блока. Сначала запиши идею и сложность."), (25, "Тестирование", "Добавь граничные случаи и объясни корректность решения.")],
                [(50, "Математика", f"Разбери математическую основу темы «{topic}» и реши 3–5 коротких задач."), (50, "SQL", "Реши три запроса: один базовый, один с JOIN/агрегацией, один на повторение."), (20, "Устный ответ", "Объясни один ML-термин и один SQL-запрос так, как на собеседовании.")],
                [(30, "Постановка", f"Выбери маленький датасет и сформулируй практическую задачу по теме «{topic}»."), (120, "Практика или мини-проект", "Сделай baseline, корректный split, реализацию метода и сохрани результаты эксперимента."), (45, "Анализ ошибок", "Найди не менее пяти ошибок модели или решения и объясни их причины."), (30, "Оформление", "Приведи ноутбук в воспроизводимый вид и запиши выводы с ограничениями."), (15, "Тренажер", "Ответь на контрольные вопросы дня.")],
                [(45, "Недельный тест", f"Без конспекта ответь на 10 вопросов по теме «{topic}» и предыдущему модулю."), (35, "Работа над ошибками", "Перерешай неверные задания и добавь слабые понятия в список повторения."), (25, "Объяснение вслух", "Запиши пятиминутное объяснение темы: идея, ограничения, метрика и пример."), (15, "Планирование", "Проверь прогресс курса и назначь один измеримый результат на следующую неделю.")],
            ]
        else:
            schedules = [
                [(55, "Теория и интервью", f"Повтори тему «{topic}» по карточкам и документации."), (45, "Вопросы собеседования", "Ответь на 8–10 вопросов с ограничением 90 секунд на ответ."), (20, "Тренажер", "Пройди встроенную проверку и выпиши слабые формулировки.")],
                [(15, "Разминка", "Повтори шаблон решения прошлой задачи."), (80, "Алгоритмы", "Реши две задачи с таймером, проговаривая идею до кода."), (25, "Разбор", "Проверь сложность, доказательство и граничные случаи.")],
                [(50, "Статистика и математика", f"Повтори математическую основу темы «{topic}» и реши 3 задачи."), (50, "ML-case", "Сформулируй данные, baseline, split, метрику и риски для одного кейса."), (20, "Тренажер", "Закрой вопросы дня без подсказок.")],
                [(90, "SQL", "Реши 4 запроса: JOIN, CTE, оконная функция и задача на даты."), (30, "Проверка", "Вручную проверь NULL, дубликаты и промежуточные таблицы.")],
                [(70, "PyTorch, NLP или LLM", f"Сделай практический эксперимент по теме «{topic}»."), (30, "Анализ результата", "Сравни с baseline по той же валидации и разбери ошибки."), (20, "Устный ответ", "Объясни эксперимент, shapes и ограничения решения.")],
                [(30, "План эксперимента", "Запиши гипотезу, одну изменяемую величину и критерий успеха."), (150, "Главный проект", f"Реализуй следующий законченный шаг проекта: {topic.lower()}."), (40, "Тесты и воспроизводимость", "Запусти проект с нуля, обнови таблицу экспериментов и README."), (20, "Итоги", "Зафиксируй результат, неудачи и следующий эксперимент.")],
                [(45, "Mock interview", "Проведи устную симуляцию: ML, проект и один уточняющий вопрос."), (30, "Разбор записи", "Выпиши неточные, длинные и неподтвержденные ответы."), (30, "Повтор слабых мест", "Переформулируй три худших ответа и повтори их без подсказок."), (15, "Планирование", "Назначь задачи и измеримый результат следующей недели.")],
            ]
        july_schedules = {
            date_type(2026, 7, 13): [(35, "Теория k-means", "Повтори шаги assign/update, функцию потерь, критерий остановки и зависимость от инициализации."), (25, "Масштаб признаков", "На четырех точках вручную сравни расстояния до и после StandardScaler."), (50, "Реализация NumPy", "Напиши k-means без sklearn: инициализация, назначение кластеров, пересчет центроидов и остановка."), (10, "Проверка", "Ответь на три вопроса по модулю 9 ниже.")],
            date_type(2026, 7, 14): [(35, "Теория PCA", "Разбери центрирование, ковариационную матрицу, собственные значения и собственные векторы."), (45, "PCA через NumPy", "Реализуй центрирование, вычисление компонент и проекцию на первые две компоненты."), (30, "Сравнение со sklearn", "Сравни результат со sklearn PCA с учетом возможной смены знака компонент."), (10, "Проверка", "Закрой вопросы по PCA.")],
            date_type(2026, 7, 15): [(55, "Домашняя работа модуля 9", "Заверши собственное решение до просмотра официального разбора."), (35, "Официальный разбор", "Сравни решения и выпиши все различия: идея, код, проверки и интерпретация."), (20, "Повтор без подсказок", "Воспроизведи самый сложный фрагмент в чистом файле."), (10, "Проверка", "Ответь на вопросы по кластеризации и PCA.")],
            date_type(2026, 7, 16): [(35, "Матричные операции", "Повтори умножение, транспонирование и смысл размеров матриц."), (35, "Ранг и линейная зависимость", "Реши задачи на ранг, базис и зависимые векторы."), (40, "Практика", "Реши 5–7 коротких задач из домашней работы модуля 8 заново."), (10, "Связь с PCA", "Объясни, зачем PCA собственные векторы и ранг.")],
            date_type(2026, 7, 17): [(20, "Сложность", "Повтори O(1), O(n), O(n log n) и O(n²) на коротких фрагментах кода."), (75, "Две задачи", "Реши две задачи на массивы, строки или словари без подсказок."), (25, "Проверка", "Добавь граничные тесты и объясни сложность каждого решения.")],
            date_type(2026, 7, 18): [(30, "Постановка", "Выбери небольшой числовой датасет и опиши, что могут означать кластеры."), (45, "Подготовка данных", "Исследуй пропуски, выбери признаки и выполни масштабирование."), (70, "PCA и k-means", "Построй Pipeline, выбери число кластеров и сохрани метрики."), (45, "Визуализация", "Покажи объекты в пространстве двух главных компонент и центроиды."), (35, "Анализ", "Объясни, полезны ли кластеры, и перечисли ограничения."), (15, "Проверка", "Закрой вопросы модуля 9.")],
            date_type(2026, 7, 19): [(45, "Контрольный тест", "Ответь без конспекта на 10 вопросов по модулям 3–9."), (35, "Список пробелов", "Раздели ошибки на математику, ML, код и интерпретацию."), (30, "Повтор", "Перерешай две ошибки с наибольшим риском для следующих тем."), (10, "План", "Зафиксируй готовность перейти к модулю 10.")],
            date_type(2026, 7, 20): [(45, "Функции и производные", "Открой семинар модуля 10 и повтори функции одной и нескольких переменных."), (35, "Частные производные", "Реши 4 коротких задачи на производные и частные производные."), (30, "Градиент", "Нарисуй линии уровня и объясни направление градиента."), (10, "Проверка", "Ответь на вопросы модуля 10.")],
            date_type(2026, 7, 21): [(40, "Выпуклость", "Разбери определение выпуклой функции и связь локального и глобального минимума."), (40, "Условия экстремума", "Реши задачи, где нулевая производная дает минимум, максимум или седловую точку."), (30, "Визуализация", "Построй графики трех функций и отметь стационарные точки."), (10, "Проверка", "Закрой вопросы по минимумам.")],
            date_type(2026, 7, 22): [(35, "Алгоритм", "Выведи шаг градиентного спуска и критерии остановки."), (55, "Линейная регрессия", "Реализуй MSE и градиентный спуск через NumPy без sklearn."), (20, "Learning rate", "Сравни три размера шага и объясни сходимость или расходимость."), (10, "Проверка", "Ответь на вопросы по оптимизации.")],
            date_type(2026, 7, 23): [(40, "Неравенства", "Реши задачи модуля 10 на функции и неравенства."), (35, "Норма и скалярное произведение", "Повтори формулы и геометрический смысл на трех задачах."), (35, "Связь с ML", "Покажи, где норма и скалярное произведение возникают в расстояниях и линейных моделях."), (10, "Проверка", "Пройди контрольные вопросы.")],
            date_type(2026, 7, 24): [(55, "Алгоритмы", "Реши две задачи без подсказок и укажи сложность."), (45, "SQL", "В SQLBolt выполни три запроса SELECT/WHERE/ORDER BY."), (20, "Разбор", "Проверь граничные случаи алгоритмов и результат SQL вручную.")],
            date_type(2026, 7, 25): [(90, "Домашняя работа модуля 10", "Реши задания самостоятельно и зафиксируй места затруднений."), (55, "Численная проверка градиентов", "Сравни аналитический градиент с конечными разностями."), (55, "Графики сходимости", "Построй loss curve для трех learning rate."), (25, "Разбор ошибок", "Сравни с официальным разбором только после своей попытки."), (15, "Проверка", "Закрой вопросы модуля 10.")],
            date_type(2026, 7, 26): [(35, "Устный ответ", "Без конспекта объясни градиент, выпуклость, learning rate и условия минимума."), (35, "Слабые задачи", "Перерешай две математические задачи, где ранее ошибся."), (30, "Повтор реализации", "Воспроизведи формулы градиента линейной регрессии."), (20, "План модуля 11", "Проверь результаты модуля 10 и назначь дату начала EDA.")],
        }
        if day in july_schedules:
            schedules[weekday] = july_schedules[day]
        if module and day not in july_schedules:
            module_schedules = {
                1: [(105, "Семинар курса", f"Открой «{module[0]}. {module[1]}» и пройди семинар последовательно, повторяя вычисления и код."), (15, "Краткий конспект", "Запиши идею темы, ключевые определения, ограничения и один пример применения.")],
                2: [(100, "Самостоятельная домашняя работа", f"Решай домашнюю работу модуля {module[0]} без официального разбора. Если в курсе указано 3 часа, оставшиеся задачи заверши в дополнительное время."), (20, "Диагностика", "Зафиксируй нерешенные пункты и точную причину каждого затруднения.")],
                3: [(45, "Завершение своей попытки", "Доведи решения до проверяемого результата до открытия разбора."), (45, "Официальный разбор", "Сравни ход решения, код и проверки. Выпиши причины ошибок."), (20, "Повтор без подсказок", "Воспроизведи самый сложный фрагмент самостоятельно."), (10, "Контроль", "Ответь на три вопроса по этому модулю ниже.")],
            }
            schedules[weekday] = module_schedules[module[2]]
        resource_sets = {
            "module9": [("Курс ВсОШ по ИИ", "Открой модуль 9 «ML. Кластеризация и методы понижения размерности»: семинар, домашняя работа или разбор по блоку дня.", ""), ("Кластеризация sklearn", "KMeans, выбор числа кластеров и примеры.", "https://scikit-learn.org/stable/modules/clustering.html"), ("PCA в sklearn", "Описание PCA, центрирования и примеры кода.", "https://scikit-learn.org/stable/modules/decomposition.html#pca")],
            "module10": [("Курс ВсОШ по ИИ", "Открой модуль 10 «Математика. Функции, неравенства и оптимизация»: семинар, домашняя работа или разбор по блоку дня.", ""), ("Производные и градиент", "Наглядное объяснение производных и градиентного спуска.", "https://www.3blue1brown.com/lessons/gradient-descent"), ("Оптимизация", "Базовые идеи оптимизации и функции потерь в ML.", "https://developers.google.com/machine-learning/crash-course/linear-regression/gradient-descent")],
            "foundation": [("Курс ВсОШ по ИИ", "Используй семинар, домашнюю работу и официальный разбор текущего модуля.", ""), ("Матрицы и PCA", "Интерактивное объяснение линейной алгебры и PCA.", "https://www.3blue1brown.com/topics/linear-algebra"), ("Документация sklearn", "KMeans, PCA и примеры использования.", "https://scikit-learn.org/stable/modules/clustering.html")],
            "validation": [("Курс ВсОШ по ИИ", "Модули 11–15: EDA, метрики и валидация.", ""), ("Валидация sklearn", "Cross-validation, split и типичные ошибки.", "https://scikit-learn.org/stable/modules/cross_validation.html"), ("Метрики sklearn", "Определения и примеры метрик моделей.", "https://scikit-learn.org/stable/modules/model_evaluation.html")],
            "models": [("Курс ВсОШ по ИИ", "Модули 16–23 и их домашние работы.", ""), ("PyTorch Tutorials", "Официальные руководства по training loop и моделям.", "https://pytorch.org/tutorials/beginner/basics/quickstart_tutorial.html"), ("Визуализатор алгоритмов", "Интерактивное повторение поиска, графов и структур данных.", "https://visualgo.net/en")],
            "nlp": [("Курс ВсОШ по ИИ", "Модули 24–29: тексты, attention и Transformer.", ""), ("Hugging Face Course", "Токенизация, Transformer и fine-tuning.", "https://huggingface.co/learn/nlp-course/chapter1/1"), ("Illustrated Transformer", "Наглядное устройство self-attention и Transformer.", "https://jalammar.github.io/illustrated-transformer/")],
            "applied": [("Google ML Crash Course", "Короткое повторение классического ML и практических решений.", "https://developers.google.com/machine-learning/crash-course"), ("SQLBolt", "Интерактивные SQL-упражнения прямо в браузере.", "https://sqlbolt.com/"), ("Hugging Face Course", "Embeddings, NLP и работа с готовыми моделями.", "https://huggingface.co/learn/nlp-course/chapter1/1")],
            "interview": [("ML System Design", "Базовые компоненты production ML-систем.", "https://developers.google.com/machine-learning/managing-ml-projects"), ("NeetCode Roadmap", "Подборка алгоритмических задач по темам.", "https://neetcode.io/roadmap"), ("SQLBolt", "Быстрая практика SQL перед интервью.", "https://sqlbolt.com/")],
        }
        resource_key = self.study_quiz_key(day)
        if module and module[0] in (9, 10):
            resource_key = f"module{module[0]}"
        if not module and day.year == 2026 and day.month == 7:
            resource_key = {
                16: "foundation", 17: "models", 18: "module9", 19: "module9",
                23: "module10", 24: "models", 25: "module10", 26: "module10",
                27: "module10", 28: "module10", 29: "module10", 30: "module10", 31: "module10",
            }.get(day.day, resource_key)
        resources = resource_sets[resource_key]
        if not module and date_type(2027, 1, 1) <= day <= date_type(2027, 5, 31):
            practicum_resources = {
                1: [("Программа ML-инженера Яндекс Практикума", "Источник тем закрепления: preprocessing, регуляризация, Optuna, SHAP и MLflow. Покупать второй курс не требуется.", "https://practicum.yandex.ru/machine-learning-start/"), ("Интерпретация моделей sklearn", "Permutation importance и анализ влияния признаков.", "https://scikit-learn.org/stable/modules/permutation_importance.html")],
                2: [("Программа ML-инженера Яндекс Практикума", "Источник тем по классическому NLP, Transformer, RAG и мультимодальности.", "https://practicum.yandex.ru/machine-learning-start/"), ("Hugging Face Course", "Практика NLP, Transformer и готовых моделей.", "https://huggingface.co/learn/nlp-course/chapter1/1")],
                3: [("Программа ML-инженера Яндекс Практикума", "Источник инженерных тем: Git, DVC, FastAPI, тестирование и Docker.", "https://practicum.yandex.ru/machine-learning-start/"), ("FastAPI Tutorial", "Создание, тестирование и документирование REST API.", "https://fastapi.tiangolo.com/tutorial/")],
                4: [("Программа ML-инженера Яндекс Практикума", "Источник тем A/B-тестирования, мониторинга и внедрения моделей.", "https://practicum.yandex.ru/machine-learning-start/"), ("Managing ML Projects", "Production ML: постановка, запуск и мониторинг.", "https://developers.google.com/machine-learning/managing-ml-projects")],
                5: [("Программа ML-инженера Яндекс Практикума", "Чек-лист практических навыков ML-инженера перед отбором.", "https://practicum.yandex.ru/machine-learning-start/"), ("NeetCode Roadmap", "Финальная практика алгоритмов по темам.", "https://neetcode.io/roadmap")],
            }
            resources = [practicum_resources[day.month][0], resources[0], practicum_resources[day.month][1]]
        if module and module[0] not in (9, 10):
            module_resources = {
                11: [("Pandas User Guide", "Пропуски, группировки и исследование табличных данных.", "https://pandas.pydata.org/docs/user_guide/index.html"), ("Seaborn Tutorial", "Графики распределений, связей и категориальных признаков.", "https://seaborn.pydata.org/tutorial.html")],
                12: [("Визуализатор алгоритмов", "Структуры данных, сортировки и пошаговое выполнение.", "https://visualgo.net/en"), ("Python: сложность операций", "Оценка операций стандартных структур Python.", "https://wiki.python.org/moin/TimeComplexity")],
                13: [("Метрики sklearn", "Формулы и примеры метрик классификации и регрессии.", "https://scikit-learn.org/stable/modules/model_evaluation.html"), ("Precision и recall", "Наглядное объяснение ошибок классификации.", "https://developers.google.com/machine-learning/crash-course/classification/accuracy-precision-recall")],
                14: [("Линейная алгебра", "Наглядные векторы, матрицы и линейные преобразования.", "https://www.3blue1brown.com/topics/linear-algebra"), ("Calculus", "Производные, градиенты и математическая интуиция.", "https://www.3blue1brown.com/topics/calculus")],
                15: [("Валидация sklearn", "Cross-validation и выбор схемы разбиения.", "https://scikit-learn.org/stable/modules/cross_validation.html"), ("Pipeline sklearn", "Как выполнять preprocessing без утечки.", "https://scikit-learn.org/stable/modules/compose.html#pipeline")],
                16: [("Бинарный поиск", "Теория и шаблоны бинарного поиска.", "https://cp-algorithms.com/num_methods/binary_search.html"), ("Практика binary search", "Задачи по теме на LeetCode.", "https://leetcode.com/tag/binary-search/")],
                17: [("Pipeline sklearn", "Генерация признаков и корректный pipeline.", "https://scikit-learn.org/stable/modules/compose.html"), ("Подбор параметров", "Grid search и randomized search.", "https://scikit-learn.org/stable/modules/grid_search.html")],
                18: [("Динамическое программирование", "Базовые идеи и задачи DP.", "https://cp-algorithms.com/dynamic_programming/intro-to-dp.html"), ("Префиксные суммы", "Техника prefix sum и примеры.", "https://usaco.guide/silver/prefix-sums")],
                19: [("PyTorch Quickstart", "Датасеты, модель, loss и optimizer.", "https://pytorch.org/tutorials/beginner/basics/quickstart_tutorial.html"), ("Backpropagation", "Наглядное устройство градиентов в нейросети.", "https://www.3blue1brown.com/lessons/backpropagation-calculus")],
                20: [("Графы", "Хранение графа, DFS и BFS.", "https://cp-algorithms.com/graph/breadth-first-search.html"), ("Визуализатор графов", "Пошаговые обходы графов.", "https://visualgo.net/en/dfsbfs")],
                21: [("Transfer Learning", "Официальный tutorial PyTorch по transfer learning.", "https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html"), ("CNN Explainer", "Интерактивная визуализация сверточной сети.", "https://poloclub.github.io/cnn-explainer/")],
                22: [("Алгоритм Дейкстры", "Кратчайшие пути от одной вершины.", "https://cp-algorithms.com/graph/dijkstra.html"), ("Floyd-Warshall", "Кратчайшие пути между всеми парами.", "https://cp-algorithms.com/graph/all-pair-shortest-path-floyd-warshall.html")],
                23: [("Автоэнкодеры", "Практический tutorial по автоэнкодерам.", "https://docs.pytorch.org/tutorials/beginner/introyt/autoencodertytutorial.html"), ("Neural Networks", "Повтор устройства нейросетей и latent representations.", "https://www.3blue1brown.com/topics/neural-networks")],
                24: [("Тернарный поиск", "Поиск экстремума унимодальной функции.", "https://cp-algorithms.com/num_methods/ternary_search.html"), ("Подмаски", "Перебор масок и подмасок.", "https://cp-algorithms.com/algebra/all-submasks.html")],
                25: [("Hugging Face NLP Course", "Токенизация и обработка текстов.", "https://huggingface.co/learn/nlp-course/chapter2/4"), ("Text sklearn", "TF-IDF и baseline классификации текста.", "https://scikit-learn.org/stable/tutorial/text_analytics/working_with_text_data.html")],
                26: [("Методы оптимизации", "Практические эвристики и задачи оптимизации.", "https://cp-algorithms.com/num_methods/simulated_annealing.html"), ("Beam Search", "Принцип лучевого поиска на последовательностях.", "https://huggingface.co/blog/how-to-generate")],
                27: [("Illustrated Attention", "RNN, перевод и механизм внимания.", "https://jalammar.github.io/visualizing-neural-machine-translation-mechanics-of-seq2seq-models-with-attention/"), ("Sequence Models", "Практика sequence models в PyTorch.", "https://pytorch.org/tutorials/beginner/nlp/sequence_models_tutorial.html")],
                28: [("Illustrated Transformer", "Self-attention, encoder и decoder.", "https://jalammar.github.io/illustrated-transformer/"), ("Hugging Face Transformers", "BERT, fine-tuning и готовые модели.", "https://huggingface.co/learn/nlp-course/chapter1/4")],
                29: [("Illustrated Stable Diffusion", "Устройство diffusion-моделей.", "https://jalammar.github.io/illustrated-stable-diffusion/"), ("CLIP", "Описание мультимодальной модели CLIP.", "https://openai.com/index/clip/")],
            }
            resources = [(f"Курс ВсОШ по ИИ · модуль {module[0]}", f"Открой «{module[0]}. {module[1]}» и выбери урок текущего дня: семинар, домашняя работа или разбор.", ""), *module_resources[module[0]]]
        blocks = [{"minutes": minutes, "title": title, "description": description}
                  for minutes, title, description in schedules[weekday]]
        return {"stage": stage, "topic": topic, "total_minutes": sum(block["minutes"] for block in blocks),
                "blocks": blocks, "resources": [{"title": title, "description": description, "url": url}
                                                 for title, description, url in resources]}

    def check_plan_answer(self):
        user, data = self.user(), self.body()
        try:
            day = date_type.fromisoformat(str(data.get("date", "")))
            drill_id = int(data.get("drill_id"))
        except (TypeError, ValueError):
            raise ApiError(400, "Некорректный вопрос")
        if day < STUDY_PLAN_START or day > STUDY_PLAN_END or drill_id not in range(3):
            raise ApiError(400, "Вопрос недоступен")
        answer = " ".join(str(data.get("answer", "")).strip().lower().replace("ё", "е").split())
        if not answer or len(answer) > 200:
            raise ApiError(400, "Введите короткий ответ")
        quiz_bank = self.quiz_bank(day)
        question = quiz_bank[(day.toordinal() % len(quiz_bank) + drill_id) % len(quiz_bank)]
        accepted = {" ".join(value.lower().replace("ё", "е").split()) for value in question[1]}
        correct = answer in accepted
        with db() as conn:
            saved = conn.execute("SELECT completed, drills_completed, quiz_version FROM study_plan_progress WHERE user_id=? AND plan_date=?",
                                 (user["id"], day.isoformat())).fetchone()
            current = saved and saved["quiz_version"] == STUDY_QUIZ_VERSION
            completed = bool(saved["completed"]) if current else False
            mask = saved["drills_completed"] if current else 0
            if correct:
                mask |= 1 << drill_id
            conn.execute("""INSERT INTO study_plan_progress(user_id,plan_date,completed,drills_completed,quiz_version,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,plan_date) DO UPDATE SET completed=excluded.completed,
                drills_completed=excluded.drills_completed, quiz_version=excluded.quiz_version, updated_at=excluded.updated_at""",
                (user["id"], day.isoformat(), int(completed), mask, STUDY_QUIZ_VERSION, now()))
        self.json_response({"correct": correct, "drills_completed": mask,
                            "explanation": question[2] if correct else "Ответ не совпал. Проверь термин или вычисление и попробуй еще раз."})

    def study_plan(self):
        user = self.user()
        start = STUDY_PLAN_START
        end = STUDY_PLAN_END
        with db() as conn:
            progress = {r["plan_date"]: r for r in conn.execute(
                "SELECT plan_date, completed, drills_completed, quiz_version FROM study_plan_progress WHERE user_id=?", (user["id"],))}
        days = []
        cursor = start
        while cursor <= end:
            item = self.study_plan_item(cursor)
            item.update(self.study_day_details(cursor))
            saved = progress.get(item["date"])
            current = saved and saved["quiz_version"] == STUDY_QUIZ_VERSION
            item["completed"] = bool(saved["completed"]) if current else False
            item["drills_completed"] = saved["drills_completed"] if current else 0
            days.append(item)
            cursor += timedelta(days=1)
        self.json_response({"start": start.isoformat(), "end": end.isoformat(), "days": days,
                            "completed": sum(item["completed"] for item in days)})

    def update_plan_day(self, plan_date):
        user, data = self.user(), self.body()
        try:
            day = date_type.fromisoformat(plan_date)
        except ValueError:
            raise ApiError(400, "Некорректная дата")
        if day < STUDY_PLAN_START or day > STUDY_PLAN_END:
            raise ApiError(400, "Дата вне периода подготовки")
        completed = bool(data.get("completed"))
        with db() as conn:
            saved = conn.execute("SELECT drills_completed, quiz_version FROM study_plan_progress WHERE user_id=? AND plan_date=?",
                                 (user["id"], plan_date)).fetchone()
            drills_completed = saved["drills_completed"] if saved and saved["quiz_version"] == STUDY_QUIZ_VERSION else 0
            if completed and drills_completed != 7:
                raise ApiError(400, "Сначала правильно ответьте на все три вопроса")
            conn.execute("""INSERT INTO study_plan_progress(user_id,plan_date,completed,drills_completed,quiz_version,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,plan_date) DO UPDATE SET completed=excluded.completed,
                drills_completed=excluded.drills_completed, quiz_version=excluded.quiz_version, updated_at=excluded.updated_at""",
                (user["id"], plan_date, int(completed), drills_completed, STUDY_QUIZ_VERSION, now()))
        self.json_response({"ok": True, "completed": completed, "drills_completed": drills_completed})

    def static(self, path):
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (PUBLIC / relative).resolve()
        if PUBLIC.resolve() not in target.parents and target != PUBLIC.resolve():
            raise ApiError(403, "Доступ запрещен")
        if not target.is_file():
            target = PUBLIC / "index.html"
        content = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") or mime == "application/javascript" else mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    init_db()
    print(f"RYD запущен: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
