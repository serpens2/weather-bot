Telegram bot made in *aiogram* able to perform weather forecasts by using [remote API](https://open-meteo.com), as well as managing a simple PostgreSQL database with users' info.

Key features:
- has an option to automatically perform daily forecast at the time of user's choosing; this is done via *apscheduler* library;
- user can send their geolocation either by turning on GPS (from the phone), or by typing in their city, or by manually finding themselves on the map with the help of [this](https://www.latlong.net/) site;
- bot generates graphs representing weather data via *matplotlib* library;
- those graphs are cached and are updated once a day;  
- all API requests, Telegram commands and *apscheduler* tasks are **asynchronous**.

## How to deploy


1. Registrate on [this](https://openweathermap.org/) site and obtain `KEY_COORDS` API-key, which is used to find geolocation given the name of the city;
2. Registrate on [this](https://www.geoapify.com/) site and obtain `KEY_TIMEZONE` API-key, which is used to find timezone given geographic coordinates;
3. Go to **@BotFather** Telegram bot and obtain `KEY_BOT` API-key, which is used to set up your own bot;
4. `git clone` this repository;
5. Create an `.env` file and write into it all the above keys (with the same names), as well as `DB_NAME`, `DB_USER`, `DB_PASSWORD` parameters of your PostgreSQL database
(all equal to 'postgres' by default);
6. In the same file write `DB_HOST="db"` (since this is the name we use in *docker-compose* file)
7. Build and run Docker container in detached mode.

## Conversation example
![1](https://github.com/user-attachments/assets/3873c823-dfcc-4373-a16a-93406ef603df)
![2](https://github.com/user-attachments/assets/3f92f5b2-cbf0-4f94-80c4-639a219f9fd5)
![3](https://github.com/user-attachments/assets/b3c8b7b2-b55c-436c-8d0f-d00cacb7a2f5)
![1352665447](https://github.com/user-attachments/assets/27bfaa9a-37e6-49e5-80bb-0cbf6394a541)
