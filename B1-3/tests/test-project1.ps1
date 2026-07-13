param(
    [Parameter(Mandatory = $true)]
    [string]$WebhookUrl
)

$cases = @(
    @{
        Name = 'Urgent branch'
        ExpectedRoute = 'URGENT'
        Body = @{
            ticket_id = 'T-001'
            requester = '테스트고객A'
            priority = 'urgent'
            subject = '결제 오류'
            message = '결제가 중복으로 처리되었습니다.'
        }
    },
    @{
        Name = 'Normal branch'
        ExpectedRoute = 'NORMAL'
        Body = @{
            ticket_id = 'T-002'
            requester = '테스트고객B'
            priority = 'normal'
            subject = '이용 방법 문의'
            message = '서비스 이용 방법을 알려주세요.'
        }
    }
)

foreach ($case in $cases) {
    $json = $case.Body | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Method Post -Uri $WebhookUrl -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
    $passed = $response.route -eq $case.ExpectedRoute

    [pscustomobject]@{
        Test = $case.Name
        Ticket = $response.ticket_id
        Expected = $case.ExpectedRoute
        Actual = $response.route
        Passed = $passed
    }
}
