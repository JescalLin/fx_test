import os
from dotenv import load_dotenv
from bfxapi import Client, REST_HOST
from datetime import datetime, timedelta
import telebot

# coin = "fUST"
coin = "fUSD"
stop_flag = False  # 停止放貸的標誌
wallet_available_balance = 0  # 錢包餘額
base_price = 150  # 基準價格
# 加載環境變數
load_dotenv(override=True)
BASE_URL = "https://api.bitfinex.com/v2"
API_KEY, API_SECRET, TG_Token, TG_chat_id = (
    os.getenv("API_KEY"),
    os.getenv("API_SECRET"),
    os.getenv("TG_Token"),
    os.getenv("TG_chat_id")
)


bfx = Client(
    rest_host=REST_HOST,
    api_key=API_KEY,
    api_secret=API_SECRET
)


# try:
#     # 獲取所有放貸訂單
#     funding_offers = bfx.rest.auth.get_funding_offers(symbol=coin)
#     print("目前的放貸訂單:")
#     for offer in funding_offers:
#         print(f"訂單 ID: {offer.id}, 金額: {offer.amount}, 匯率: {offer.rate}, 天數: {offer.period}")

#     # 檢查是否有放貸訂單
#     if funding_offers:
#         print("正在取消所有放貸訂單...")
#         for offer in funding_offers:
#             try:
#                 # 取消每個訂單
#                 cancel_response = bfx.rest.auth.cancel_funding_offer(id=offer.id)
#                 print(f"取消訂單成功: 訂單 ID: {offer.id}, 回應: {cancel_response}")
#             except Exception as e:
#                 print(f"無法取消訂單 ID: {offer.id}, 錯誤: {e}")
#     else:
#         print("目前沒有放貸訂單可取消。")
# except Exception as e:
#     print(f"無法獲取放貸訂單: {e}")

print("-----------------------------------------")
# 獲取融資錢包中的餘額
try:
    msg = ""
    wallets = bfx.rest.auth.get_wallets()  # 獲取所有錢包資訊
    for wallet in wallets:
        if wallet.wallet_type == 'funding' and wallet.currency == "USD":
            print(f"融資錢包中的 USD 餘額: {wallet.balance}")
            print(f"可用餘額: {wallet.available_balance}")
            msg += f"融資錢包中的 USD 餘額: {wallet.balance}\n"
            msg += f"可用餘額: {wallet.available_balance}\n"
            wallet_available_balance = wallet.available_balance
            if int(wallet_available_balance) < 150: 
                print(f"可用餘額: {wallet_available_balance}，小於150，暫停放貸。")
                msg += f"可用餘額: {wallet_available_balance}，小於150，暫停放貸。\n"
                stop_flag = True
            print(f"未結算利息: {wallet.unsettled_interest}")
except Exception as e:
    print(f"無法獲取錢包資訊: {e}")
print("-----------------------------------------")


try:
    bot = telebot.TeleBot(TG_Token)
    if len(msg) > 4095:
        for x in range(0, len(msg), 4095):
            bot.send_message(TG_chat_id, text=msg[x:x+4095])
    else:
        bot.send_message(TG_chat_id, text=msg)
except Exception as e:
    print(f"無法發送消息到 Telegram: {e}")

if stop_flag == True: 
    pass
else:
    # 策略參數
    LENDING_AMOUNT = base_price  # 放貸總金額
    LENDING_PERIOD = 2  # 放貸天數
    RATE_THRESHOLD = [0.0003, 0.0004, 0.0005, 0.0006, 0.0007, 0.0008]  # 匯率門檻
    Y_RATE_THRESHOLD = []
    for i in range(len(RATE_THRESHOLD)):
        annual_rate = RATE_THRESHOLD[i] * 365  # 將日利率轉換為年利率
        #print(f"門檻{i}，年利率: {annual_rate * 100:.2f}%")
        Y_RATE_THRESHOLD.append(f"{annual_rate * 100:.2f}%")
    print("-----------------------------------------")

    # 獲取市場放貸匯率數據
    lending_rates = bfx.rest.public.get_f_raw_book(currency=coin)
    if lending_rates:
        valid_rates_n = [rate for rate in lending_rates]
        # 過濾出匯率高於門檻的數據
        valid_rates = [rate for rate in lending_rates if rate.rate >= RATE_THRESHOLD[0]]

        if valid_rates:
            msg = ""
            # 找到最高匯率
            best_rate = max(valid_rates, key=lambda x: x.rate)
            best_rate_rate = best_rate.rate
            best_rate_amount =  best_rate.amount
            best_rate_period =  best_rate.period
            #best_rate_rate = RATE_THRESHOLD[5]  # 測試用，實際使用時請刪除這行
            annual_rate = best_rate_rate * 365  # 將日利率轉換為年利率
            print(f"目前最佳年利率: {annual_rate * 100:.2f}% " + str(best_rate_period)+"天 " + str(best_rate_amount)+" USD")
            msg += f"目前最佳年利率: {annual_rate * 100:.2f}% " + str(best_rate_period)+"天 " + str(best_rate_amount)+" USD\n"
            level = 0
            for i in range(len(RATE_THRESHOLD)):
                if best_rate_rate >= RATE_THRESHOLD[i]:
                    level = i
            print(f"目前門檻: {level} : {Y_RATE_THRESHOLD[level]}")
            msg += f"目前門檻: {level} : {Y_RATE_THRESHOLD[level]}\n"

            if level == 0 :
                LENDING_AMOUNT = base_price
                LENDING_PERIOD = 2
            if level == 1 :
                LENDING_AMOUNT = base_price + 25
                LENDING_PERIOD = 2
            if level == 2 :
                LENDING_AMOUNT = base_price + 50
                if best_rate_period > 5:
                    LENDING_PERIOD = 5
                else:
                    LENDING_PERIOD = best_rate_period
            if level == 3 :
                LENDING_AMOUNT = base_price + 50
                if best_rate_period > 10:
                    LENDING_PERIOD = 10
                else:
                    LENDING_PERIOD = best_rate_period
            if level == 4 :
                LENDING_AMOUNT = base_price + 100
                if best_rate_period > 15:
                    LENDING_PERIOD = 15
                else:
                    LENDING_PERIOD = best_rate_period
            # 根據匯率門檻進一步調整天數
            if level == 5:  # 如果匯率超過最高門檻
                if best_rate_period > 30:
                    LENDING_PERIOD = 30  # 鎖定高匯率，延長放貸天數
                else:
                    LENDING_PERIOD = best_rate_period
                
                LENDING_AMOUNT = int(wallet_available_balance)


            if int(wallet_available_balance) - LENDING_AMOUNT < base_price:
                LENDING_AMOUNT = int(wallet_available_balance)


            print(f"調整後的放貸金額: {LENDING_AMOUNT}")
            print(f"調整後的放貸天數: {LENDING_PERIOD}")
            msg += f"調整後的放貸金額: {LENDING_AMOUNT}\n"
            msg += f"調整後的放貸天數: {LENDING_PERIOD}\n"

            
            # 計算預估收益
            daily_rate = best_rate.rate
            total_interest = LENDING_AMOUNT * daily_rate * LENDING_PERIOD
            total_amount = LENDING_AMOUNT + total_interest
            print(f"預估收益: {total_interest:.6f}，總金額: {total_amount:.6f}")
            msg += f"預估收益: {total_interest:.6f}，總金額: {total_amount:.6f}\n"

            # 執行放貸操作
            try:
                response = bfx.rest.auth.submit_funding_offer(
                    type="LIMIT",  # 放貸類型
                    symbol=coin,
                    amount=str(LENDING_AMOUNT),  # 放貸金額
                    rate=best_rate.rate,  # 匯率
                    period=LENDING_PERIOD  # 放貸天數
                )
                print("放貸成功:", response)
                msg += f"放貸成功: {response}\n"

                if int(wallet_available_balance)-LENDING_AMOUNT > 150:
                    response = bfx.rest.auth.submit_funding_offer(
                        type="LIMIT",  # 放貸類型
                        symbol=coin,
                        amount=str(int(wallet_available_balance)-LENDING_AMOUNT),  # 放貸金額
                        rate="0.00055",  # 匯率
                        period=2  # 放貸天數
                    )

                bot = telebot.TeleBot(TG_Token)

                if len(msg) > 4095:
                    for x in range(0, len(msg), 4095):
                        bot.send_message(TG_chat_id, text=msg[x:x+4095])
                else:
                    bot.send_message(TG_chat_id, text=msg)



            except Exception as e:
                print("放貸失敗:", e)
        else:
            msg = ""
            best_rate = max(valid_rates_n, key=lambda x: x.rate)
            print(best_rate)
            best_rate_rate = best_rate.rate
            best_rate_amount =  best_rate.amount
            best_rate_period =  best_rate.period
            #best_rate_rate = RATE_THRESHOLD[6]  # 測試用，實際使用時請刪除這行
            annual_rate = best_rate_rate * 365  # 將日利率轉換為年利率
            print(f"目前最佳日利率:{best_rate_rate}")
            print(f"目前最佳年利率: {annual_rate * 100:.2f}% " + str(best_rate_period)+"天 " + str(best_rate_amount)+" USD")
            print("無有效匯率高於門檻，暫停放貸。")

            msg += f"目前最佳日利率:{best_rate_rate}\n"
            msg += f"目前最佳年利率: {annual_rate * 100:.2f}% " + str(best_rate_period)+"天 " + str(best_rate_amount)+" USD\n"
            msg += "無有效匯率高於門檻，暫停放貸。\n"

            bot = telebot.TeleBot(TG_Token)
            if len(msg) > 4095:
                for x in range(0, len(msg), 4095):
                    bot.send_message(TG_chat_id, text=msg[x:x+4095])
            else:
                bot.send_message(TG_chat_id, text=msg)


    else:
        print("無法獲取放貸匯率數據")
