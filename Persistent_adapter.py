import willump
import json
import pickle
import asyncio
import logging

def main():
    # Open a subscription and filter it to summoners 0 endpoint
    # and set the handler to print the data
    async def brr():
        wllp = await willump.start()
        all_events_subscription = await wllp.subscribe(
            'OnJsonApiEvent', default_handler=None)
        # all_events_subscription = await wllp.subscribe(
        #     'OnJsonApiEvent_lol-champ-select_v1_session', default_handler=summoner_0_handler)
        all_events_subscription.filter_endpoint(
            '/lol-champ-select/v1/session',
            handler=printer)
        # logging.basicConfig(level=logging.DEBUG)
        while True:
            await asyncio.sleep(1)

    # Define the handler function
    async def printer(data):
        print('Data is: ', data)

    asyncio.run(brr())


if __name__ == '__main__':
    main()
