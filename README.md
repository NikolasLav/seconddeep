# seconddeep
 Вторая попытка. 3 фотографии

 А точнее вторая версия поисковика, но теперь уже с выдачей 3-х самых рейтинговых фотографии пользователя.
 Что хотелось бы отметить:
Реализован функционал (Дополнительные требования):
* В vk максимальная выдача при поиске 1000 человек. Подумать как это ограничение можно обойти.
	- Можно обойти только в случае поиска по каждому году, но для этого нужно, чтобы диапазон "ОТ" и "ДО"
	был не меньше 4-х лет. Опять
	НИКАК нельзя обойти, в т.ч. через offset.
	Целесообразно реализовать в асинхронном режиме, из-за длительности выполнения запросов, и довольно
	большого объёма реквеста (получаемого ответа от сервера).
* Добавить возможность ставить/убирать лайк, выбранной фотографии.
	- реализовано
* Добавлять человека в избранный список, используя БД
	- реализовано, через лайк к фотографии
* Добавлять человека в черный список чтобы он больше не попадался при поиске, используя БД
	- зачем, если есть условие в требованиях к сервису "Люди не должны повторяться при повторном поиске."
	Если только при очистке результатов сохранять ЧС? Организовать легко.
* К списку фотографий из аватарок добавлять список фотографий, где отмечен пользователь.
	- реализовано. Возвращает топ-3 (если есть, или меньше) фото, на кот. отмечен пользователь.
	- в виде фото отображаются только те, что доступны сообществу. чтобы отправить сообщение с аттачем от пользователя
	нужно следовать инструкции https://vk.com/dev/messages_api. Для учебных целей не целесообразно запрашивать "в 
	Поддержке тестовый доступ, подразумевающий работу методов секции Messages с ключами администраторов
	Вашего Standalone-приложения."

 1. Версия получилась многопользовательской, но однопоточной. Сейчас объясню...
 В классе Bot хранится словарь пользователей с идентификатором по их ID в VK. Хранится в течении жизни сессии.
 Легко обновляется и быстрее доступ, чем из БД SQL.
 2. Ботом может пользоваться любой пользователь, если ему не запрещены отправки сообщений от сообществ.
 Желательно состоять в сообществе (не проверял).
 3. Отказался от реализации SQLAlchemy в данном проекте, т.к. изучение вопроса о библиотеке дало представление о
 иногда неверном формировании запросов. Решил не привыкать к "плохому". Вопрос, конечно, спорный. Но практику по
 этой библиотеке я сдал.
 В моей работе "чистые" SQL-запросы.
 4. По совету одного из преподавателей постарался минимизировать используемое пространство в БД. Меджу сессиями
 достаточно сохранять лишь результаты - остальное лучше обновлять (данные пользователя - это быстро; данные для поиска-
 будут как раз самые АКТУАЛЬНЫЕ).
 5. Не реализовал, хотя мог множество функций, типа весов и сравнения интересов, т.к. в однопоточном (синхронном)
 режиме выполнения это серьёзно повлияет на ожидание результата. И я, как раз взялся за новый подход - реализация
 приложения в асинхронном режиме. Надеюсь успеть сдать оба варианта.
 6. Так же неясно выполнение дополнительных требований по соблюдению нормы весов критериев поиска: нужно рейтинговать
 результат поиска или всю выборку полученную из users.search? Немного непонятно, приходится очень много додумывать
 в этом плане. Если бы был в ТЗ конкретный пример, или более подробное описание работы весов - это бы сэкономило массу
 времени.
 7. Это невероятный опыт работы! Спасибо за него! Мой первый серьёзный кейс :)