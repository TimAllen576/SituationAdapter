import pickle


teammate_champ = 'Illaoi'
anvils = []

pickable_ids = list(range(1000))
with open('mapping_champ_to_id.pkl', 'rb') as file:
    mapping_champ_to_id = pickle.load(file)
with open('arena_champs_ranking.pkl', 'rb') as file:
    arena_champs_ranking = pickle.load(file)
with open('Situations_Adapted_To.pkl', 'rb') as file:
    completed_ids = pickle.load(file)
anvil_ids = []
for anvil in anvils:
    anvil_ids.append(mapping_champ_to_id[anvil])
best_playable_synergies = []
anvil_synergies = []
for champ in arena_champs_ranking[teammate_champ]:
    if champ is None:
        continue
    champ_id = mapping_champ_to_id[champ]
    if champ_id not in completed_ids and champ_id in pickable_ids:
        if champ_id in anvil_ids:
            anvil_synergies.append(champ)
        else:
            best_playable_synergies.append(champ)
if len(best_playable_synergies) == 0:
    for champ in arena_champs_ranking['']:
        if champ is None:
            continue
        champ_id = mapping_champ_to_id[champ]
        if champ_id not in completed_ids and champ_id in pickable_ids:
            best_playable_synergies.append(champ)
print('Anvil synergies:')
print(*anvil_synergies, sep='\n')
print(f'Best playable synergies:')
print(*best_playable_synergies[:5], sep='\n')

print(arena_champs_ranking)
# print(len(completed_ids))

# completed_list = []
# for id in completed_ids:
#     # reverse the id mapping
#     for champ in mapping_champ_to_id:
#         if mapping_champ_to_id[champ] == id:
#             completed_list.append(champ)
#             break
# print('Completed synergies:')
# completed_list.sort()
# print(*completed_list, sep='\n')
