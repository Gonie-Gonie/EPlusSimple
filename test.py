from epsimple import GreenRetrofitModel, Profile

grm = GreenRetrofitModel.from_grjson("./examples/grm/ASHRAE 140 modified.grm")

for profile in Profile.get_DB("__all__"):
    
    grm.zone[0].profile = profile
    grr = grm.run()
    pass