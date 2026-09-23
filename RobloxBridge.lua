--!strict
-- AI Bridge v1 — Studio Lite ↔ AI
local HttpService = game:GetService("HttpService")
local REPL_URL = "https://your-app.onrender.com"  -- رابط السيرفر الوسيط
local API_KEY  = "MY_SECRET_KEY_123"
local SESSION  = "map1"
local POLL_DELAY = 1.5

local headers = {["X-Auth"] = API_KEY, ["Content-Type"] = "application/json"}

-- قائمة الأوامر المسموحة (White-list — أمان وأدقّ من eval)
local Actions = {}

Actions.createPart = function(args)
	local p = Instance.new(args.className or "Part")
	p.Size = args.size or Vector3.new(4,1,4)
	p.Position = args.position or Vector3.new(0,10,0)
	p.Anchored = args.anchored ~= false
	p.Color = args.color and Color3.fromRGB(args.color[1], args.color[2], args.color[3]) or Color3.new(1,1,1)
	p.Name = args.name or "AIPart"
	p.Parent = workspace
	return {instance = p:GetFullName()}
end

Actions.delete = function(args)
	local target = workspace:FindFirstChild(args.name, true)
	if target then target:Destroy() return {deleted = true} end
	return {error = "not found"}
end

Actions.setProperty = function(args)
	local inst = workspace:FindFirstChild(args.name, true)
	if not inst then return {error = "not found"} end
	-- تُنفّذ بأمان عبر قيم محددة فقط
	local allowed = {["Anchored"]=true,["Transparency"]=true,["Name"]=true,["Position"]=true,["Size"]=true,["Color"]=true}
	local prop = args.property
	if not allowed[prop] then return {error = "property not allowed"} end
	local v = args.value
	if prop == "Position" or prop == "Size" then v = Vector3.new(v[1], v[2], v[3])
	elseif prop == "Color" then v = Color3.fromRGB(v[1], v[2], v[3]) end
	(inst :: any)[prop] = v
	return {set = true}
end

Actions.ping = function(_) return {pong = true, time = os.time()} end
Actions.scriptCommand = function(args)  -- أمر حرّ (اختياري ومحاذَر)
	local fn, err = loadstring(args.code)
	if not fn then return {error = err} end
	local ok, res = pcall(fn)
	return {ok = ok, result = tostring(res)}
end

local function reply(cmdId, action, result)
	local body = HttpService:JSONEncode({
		session = SESSION, cmdId = cmdId, action = action,
		result = result, ok = result.error == nil,
	})
	pcall(function()
		HttpService:PostAsync(REPL_URL .. "/result", body, Enum.HttpContentType.ApplicationJson, false, headers)
	end)
end

task.spawn(function()
	while true do
		local ok, res = pcall(function()
			return HttpService:GetAsync(REPL_URL .. "/poll?session=" .. SESSION, false, headers)
		end)
		if ok then
			for _, cmd in HttpService:JSONDecode(res).commands do
				local handler = Actions[cmd.action]
				local result
				if handler then
					local okExec, r = pcall(handler, cmd.args or {})
					result = okExec and r or {error = tostring(r)}
				else
					result = {error = "unknown action: " .. tostring(cmd.action)}
				end
				reply(cmd.id, cmd.action, result)
			end
		else
			warn("[AI-Bridge] poll failed: " .. tostring(res))
		end
		task.wait(POLL_DELAY)
	end
end)
print("[AI-Bridge] running — session:", SESSION)
