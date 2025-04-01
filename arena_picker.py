import asyncio
import pickle
import time
import logging
from io import BytesIO
import willump
import pycurl
import bs4
import numpy as np
import pandas as pd

teammate_champ = ''
pickable_ids = []
teammate_update_count = 0
pickable_update_count = 0

async def update_champ_mapping():
    wllp = await willump.start()
    available_champs_response = await wllp.request('get', '/lol-champions/v1/owned-champions-minimal')
    available_champs = await available_champs_response.json()
    mapping_champ_to_id = {}
    for champ in available_champs:
        mapping_champ_to_id[champ['name']] = champ['id']
    with open('mapping_champ_to_id.pkl', 'wb') as file:
        pickle.dump(mapping_champ_to_id, file)
    logging.debug('Champ mapping updated')
    await wllp.close()

def update_synergies_opgg():
    with open('mapping_champ_to_id.pkl', 'rb') as file:
        mapping_champ_to_id = pickle.load(file)
    synergy_list = []
    index_list = []
    for champ_name in mapping_champ_to_id.keys():
        logging.debug(f'Getting synergies for {champ_name}')
        synergy_list.append(get_synergies_opgg(champ_name))
        logging.debug(f'Got synergies for {champ_name}')
        index_list.append(champ_name)
    synergy_df = pd.DataFrame(synergy_list, index=index_list).T
    synergy_df[''] = get_overall_opgg()[0:synergy_df.shape[0]]
    with open('arena_champs_ranking.pkl', 'wb') as file:
        pickle.dump(synergy_df, file)

def get_synergies_opgg(champ_name):
    url_name = champ_name.replace(' ', '').replace('.', '').replace("'", '').lower()
    if champ_name == 'Nunu & Willump':
        url_name = 'nunu'
    elif champ_name == 'Wukong':
        url_name = 'monkeyking'
    elif champ_name == 'Renata Glasc':
        url_name = 'renata'
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL,
             f"https://www.op.gg/modes/arena/{url_name}/synergies?region=global&patch=15.06")
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    body = buffer.getvalue()
    soup = bs4.BeautifulSoup(body, 'html.parser')
    synergy_table = soup.find(
        'caption', string=f'{champ_name} synergies').find_parent('table')
    champ_infos = synergy_table.find_next('tbody').find_all('td')
    champ_info_list = []
    for td in champ_infos:
        champ_info_list.append(td.text)
    champ_info_df = pd.DataFrame(
        np.array(champ_info_list).reshape(-1, 5),
        columns=[
            'Champion', 'Average Place', 'First Rate', 'Win Rate', 'Pick Rate'
        ]).sort_values(by='First Rate', ascending=False, key=series_str_percent_int)
    return champ_info_df['Champion'].values

def get_overall_opgg():
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(
        c.URL,
        f"https://www.op.gg/modes/arena")
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    body = buffer.getvalue()
    soup = bs4.BeautifulSoup(body, 'html.parser')
    champion_table = soup.find('caption', string='Champions Rank').find_parent('table')
    champ_infos = champion_table.find_next('tbody').find_all('tr')
    champ_info_list = []
    for tr in champ_infos:
        champ_name = tr.find_next('strong').text
        win_rate = tr.find_all('td')[-1].text
        champ_info_list.append([champ_name, win_rate])
    champ_info_df = pd.DataFrame(champ_info_list, columns=['Champion', 'Win Rate']
                                 ).sort_values(
        by='Win Rate', ascending=False, key=series_str_percent_int)['Champion'].values
    return champ_info_df

def series_str_percent_int(series):
    """Helper func for sorting,
    turns series of percent strings in representative ints"""
    rep_list = []
    for string in series:
        rep_int = int(float(string.strip('%'))*100)
        rep_list.append(rep_int)
    return pd.Series(rep_list)

async def update_completions():
    wllp = await willump.start()
    challenges_response = await wllp.request('get', '/lol-challenges/v1/challenges/local-player')
    challenges_json = await challenges_response.json()
    with open('Situations_Adapted_To.pkl', 'wb') as file:
        pickle.dump(challenges_json['602002']['completedIds'], file)
    logging.debug('Completions updated')
    await wllp.close()

async def check_for_champ_select():
    wllp = await willump.start()
    in_champ_select = False
    while not in_champ_select:
        session_response = await wllp.request(
            'get', '/lol-champ-select/v1/session')
        session_json = await session_response.json()
        try:
            local_player_cell_id = session_json["localPlayerCellId"]
            in_champ_select = True
            await get_champ_select_info(local_player_cell_id, wllp)
        except KeyError:
            logging.debug('Not in champ select yet')
            await asyncio.sleep(1)
    await wllp.close()

async def get_champ_select_info(local_player_cell_id, wllp):
    # TODO Handle dodges
    if local_player_cell_id % 2 == 0:
        teammate_cell_id = local_player_cell_id + 1
    else:
        teammate_cell_id = local_player_cell_id - 1
    everything_subscription = await wllp.subscribe(
        'OnJsonApiEvent', default_handler=None)
    wllp.subscription_filter_endpoint(
        everything_subscription, f'/lol-champ-select/v1/summoners/{teammate_cell_id}',
    handler=update_teammate_champ)
    wllp.subscription_filter_endpoint(
        everything_subscription, '/lol-champ-select/v1/pickable-champion-ids',
        handler=update_pickable_ids)
    for _ in range(5):
        await asyncio.sleep(0.1)
    if teammate_update_count == 0 or pickable_update_count == 0:
        print(f'Update counts received are '
              f'{teammate_update_count} and {pickable_update_count}')
        pickable_response = await wllp.request(
            'get', '/lol-champ-select/v1/pickable-champion-ids')
        pickable_info = await pickable_response.json()
        await update_pickable_ids(pickable_info)
        teammate_response = await wllp.request(
            'get', f'/lol-champ-select/v1/summoners/{teammate_cell_id}')
        teammate_info = await teammate_response.json()
        await update_teammate_champ(teammate_info)
    for _ in range(100):
        logging.debug('Waiting for updates')
        await asyncio.sleep(1)

async def update_teammate_champ(data):
    global teammate_champ
    global teammate_update_count
    teammate_champ = data['championName']
    teammate_update_count += 1
    show_synergies()

async def update_pickable_ids(data):
    global pickable_ids
    global pickable_update_count
    pickable_ids = data
    pickable_update_count += 1
    show_synergies()

def show_synergies():
    print(f'Teammate champ: {teammate_champ}')
    with open('mapping_champ_to_id.pkl', 'rb') as file:
        mapping_champ_to_id = pickle.load(file)
    with open('arena_champs_ranking.pkl', 'rb') as file:
        arena_champs_ranking = pickle.load(file)
    with open('Situations_Adapted_To.pkl', 'rb') as file:
        completed_ids = pickle.load(file)
    best_playable_synergies = []
    for champ in arena_champs_ranking[teammate_champ]:
        champ_id = mapping_champ_to_id[champ]
        if champ_id not in completed_ids and champ_id in pickable_ids:
            best_playable_synergies.append(champ)
    if len(best_playable_synergies) == 0:
        logging.debug('No playable synergies found')
        for champ in arena_champs_ranking['']:
            champ_id = mapping_champ_to_id[champ]
            if champ_id not in completed_ids and champ_id in pickable_ids:
                best_playable_synergies.append(champ)
    print(f'Best playable synergies:')
    print(*best_playable_synergies[:5], sep='\n')

def main():
    # asyncio.run(update_champ_mapping())
    # update_synergies_opgg()
    # asyncio.run(update_completions())
    # logging.basicConfig(level=logging.DEBUG)
    while True:
        asyncio.run(check_for_champ_select())
        time.sleep(1)


if __name__ == "__main__":
    main()
