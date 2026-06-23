from epsimple import Profile, run_grjson

epsprofile     = Profile.get_DB("소규모사무실")
idragonprofile = epsprofile.to_dragon()


result = run_grjson("./examples/grm/ASHRAE 140 modified.grm")

pass