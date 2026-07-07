from update_mods import extract_readme_game_names, flag_multigame_gaps

TABLE = """# DragonTweak
Some intro text.

### Current Features
| Game                           | Feature A | Feature B |
|--------------------------------|-----------|-----------|
| Yakuza 0                       | ✔️        | ❌        |
| Yakuza Kiwami                  | ✔️        | ✔️        |
| Like a Dragon: Infinite Wealth | ✔️        | ✔️        |

## Installation
- Extract the zip.
"""


def test_extract_game_names_from_table():
    assert extract_readme_game_names(TABLE) == [
        "Yakuza 0", "Yakuza Kiwami", "Like a Dragon: Infinite Wealth"]


def test_extract_ignores_header_separator_and_prose():
    assert extract_readme_game_names("no tables\njust prose") == []
    # a table whose only rows are header+separator yields nothing
    assert extract_readme_game_names("| Game |\n|------|\n") == []


def test_flag_multigame_gaps_finds_new_game():
    mods = {
        "DragonTweak": {"repo": "Lyall/DragonTweak",
                        "games": [{"steam_appid": 1}, {"steam_appid": 2}]},
        "SingleFix": {"repo": "Lyall/SingleFix", "games": [{"steam_appid": 9}]},
    }
    readmes = {"Lyall/DragonTweak": "| Game |\n|---|\n| GameA |\n| GameB |\n| GameC |\n"}
    appids = {"GameA": 1, "GameB": 2, "GameC": 3}
    warns = flag_multigame_gaps(mods, fetch_readme=lambda r: readmes.get(r),
                                resolve_appid=lambda n: appids.get(n))
    assert any("GameC" in w and "3" in w for w in warns)
    assert not any("GameA" in w or "GameB" in w for w in warns)   # already covered
    assert not any("SingleFix" in w for w in warns)               # single-game skipped


def test_flag_skips_missing_readme():
    mods = {"M": {"repo": "r", "games": [{"steam_appid": 1}, {"steam_appid": 2}]}}
    assert flag_multigame_gaps(mods, fetch_readme=lambda r: None,
                               resolve_appid=lambda n: 3) == []


def test_flag_ignores_unresolvable_and_already_covered():
    mods = {"M": {"repo": "r", "games": [{"steam_appid": 1}, {"steam_appid": 2}]}}
    readmes = {"r": "| Game |\n|---|\n| X |\n| Y |\n"}
    # X can't be resolved (None), Y resolves to an appid already in the catalog
    warns = flag_multigame_gaps(mods, fetch_readme=lambda r: readmes[r],
                                resolve_appid=lambda n: {"Y": 2}.get(n))
    assert warns == []


def test_flag_dedupes_repeated_new_appid():
    mods = {"M": {"repo": "r", "games": [{"steam_appid": 1}, {"steam_appid": 2}]}}
    readmes = {"r": "| Game |\n|---|\n| A |\n| A again |\n"}
    warns = flag_multigame_gaps(mods, fetch_readme=lambda r: readmes[r],
                                resolve_appid=lambda n: 5)  # both resolve to 5
    assert len(warns) == 1


def test_flag_skips_demo_titles():
    mods = {"M": {"repo": "r", "games": [{"steam_appid": 1}, {"steam_appid": 2}]}}
    readmes = {"r": "| Game |\n|---|\n| Cool Game (Demo) |\n| Real Game |\n"}
    appids = {"Cool Game (Demo)": 100, "Real Game": 200}
    warns = flag_multigame_gaps(mods, fetch_readme=lambda r: readmes[r],
                                resolve_appid=lambda n: appids.get(n))
    assert any("Real Game" in w for w in warns)
    assert not any("Demo" in w for w in warns)
